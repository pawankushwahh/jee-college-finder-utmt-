"""Core recommendation pipeline: take a student profile and return a filtered,
categorized and interest-ranked list of institute + branch options.
"""

from __future__ import annotations

from typing import List, Optional

from . import states
from .data_loader import (
    Program,
    female_seat_advantage_index,
    home_state_advantage_index,
    load_programs,
)
from .schemas import (
    CategoryGuidance,
    Recommendation,
    RecommendRequest,
    RecommendResponse,
)

# How far past the closing rank we still treat an option as a (Reach) possibility.
UPPER_MARGIN = 0.25
# How far below the opening rank before we consider the student "overqualified"
# (i.e. they should be aiming materially higher) and drop the option.
LOWER_MARGIN = 0.50

# ---------------------------------------------------------------------------
# Confidence band thresholds, derived from this dataset's rank-spread
# (closing - opening) distribution: median ~3,200, p25 ~1,040, p66 ~5,950, and
# 235 rows where closing <= opening (a zero/inverted window).
#   - "fragile": spread < 1,000 (tight window), or closing <= opening (always).
#   - "high":    spread >= 6,000 (a wide, stable window that absorbs swings).
#   - "medium":  everything in between (the bulk, around the median).
# A wider last-year window means the cutoff is less likely to shift past you.
# ---------------------------------------------------------------------------
FRAGILE_MAX_SPREAD = 1_000
HIGH_MIN_SPREAD = 6_000

# Display order of the three buckets.
CATEGORY_ORDER = {"Target": 0, "Reach": 1, "Safe": 2}

# ---------------------------------------------------------------------------
# User-facing text, keyed by language ("en" / "hi"). Hindi is natural, simple
# Devanagari; technical terms (CSE, NIT, IIT, Target/Reach/Safe) stay in
# English where students expect them.
# ---------------------------------------------------------------------------
FIT_LABELS = {
    "en": {
        "Safe": "Comfortable - your rank is better than last year's opening rank.",
        "Target": "Achievable - your rank lies within last year's opening to closing range.",
        "Reach": "Ambitious - just beyond last year's closing rank, but worth a try.",
    },
    "hi": {
        "Safe": "आरामदायक — आपकी रैंक पिछले साल की ओपनिंग रैंक से बेहतर है।",
        "Target": "हासिल करने लायक — आपकी रैंक पिछले साल की ओपनिंग से क्लोज़िंग रेंज के बीच है।",
        "Reach": "महत्वाकांक्षी — पिछले साल की क्लोज़िंग रैंक से थोड़ा आगे, पर कोशिश के लायक।",
    },
}

CATEGORY_BLURBS = {
    "en": {
        "Target": (
            "These match your rank closely (within last year's opening-closing "
            "window). They are your most realistic picks."
        ),
        "Reach": (
            "These closed slightly above your rank last year. Cutoffs fluctuate, so "
            "list a few as ambitious choices."
        ),
        "Safe": (
            "Your rank comfortably beats last year's opening rank here, so these are "
            "strong backups you are very likely to get."
        ),
    },
    "hi": {
        "Target": (
            "ये आपकी रैंक से क़रीब से मेल खाते हैं (पिछले साल की ओपनिंग-क्लोज़िंग रेंज के "
            "अंदर)। ये आपके सबसे realistic विकल्प हैं।"
        ),
        "Reach": (
            "ये पिछले साल आपकी रैंक से थोड़ा ऊपर बंद हुए थे। कटऑफ़ बदलते रहते हैं, इसलिए "
            "कुछ को महत्वाकांक्षी विकल्प के तौर पर रखें।"
        ),
        "Safe": (
            "आपकी रैंक यहाँ पिछले साल की ओपनिंग रैंक से आराम से बेहतर है, इसलिए ये मज़बूत "
            "बैकअप हैं जो आपको मिलने की पूरी संभावना है।"
        ),
    },
}


def _relevant_rank(prog: Program, req: RecommendRequest) -> Optional[int]:
    return req.adv_rank if prog.exam == "advanced" else req.mains_rank


def _passes_gender(prog: Program, gender: str) -> bool:
    if gender == "female":
        return True  # female applicants are eligible for both pools
    return prog.gender_pool == "neutral"


def _passes_quota(prog: Program, home_state: str) -> bool:
    quota = prog.quota
    if prog.institute_type == "IIT" or quota == "AI":
        return True
    if quota == "HS":
        return prog.institute_state == home_state
    if quota == "OS":
        return prog.institute_state != home_state
    if quota in states.SPECIAL_QUOTA_STATE:
        return states.SPECIAL_QUOTA_STATE[quota] == home_state
    return True


def _categorize(rank: int, opening: int, closing: int) -> Optional[str]:
    """Return Safe/Target/Reach, or None if the option should be dropped."""
    if rank > closing * (1 + UPPER_MARGIN):
        return None  # no realistic chance
    if rank < opening * (1 - LOWER_MARGIN):
        return None  # heavily overqualified - aim higher
    if rank <= opening:
        return "Safe"
    if rank <= closing:
        return "Target"
    return "Reach"


def _interest_score(prog: Program, goal: str) -> tuple[float, bool]:
    weights = states.GOAL_TAG_WEIGHTS.get(goal, {})
    base = max((weights.get(t, 0) for t in prog.tags), default=0)
    brand_sensitivity = states.GOAL_BRAND_SENSITIVE.get(goal, 0.0)
    score = base + brand_sensitivity * prog.brand_score * 5.0
    return float(score), base > 0


def _confidence(opening: int, closing: int) -> str:
    """Classify how stable last year's window is, from its rank spread."""
    spread = closing - opening
    if spread <= 0 or spread < FRAGILE_MAX_SPREAD:
        return "fragile"
    if spread >= HIGH_MIN_SPREAD:
        return "high"
    return "medium"


_BRAND_PHRASES = {
    "en": {
        "top_iit": "a top IIT",
        "iit": "an IIT",
        "top_nit": "a top NIT",
        "nit": "an NIT",
        "iiit": "an IIIT",
        "gfti": "a government-funded institute",
    },
    "hi": {
        "top_iit": "एक टॉप IIT",
        "iit": "एक IIT",
        "top_nit": "एक टॉप NIT",
        "nit": "एक NIT",
        "iiit": "एक IIIT",
        "gfti": "एक सरकारी संस्थान",
    },
}


def _brand_phrase(prog: Program, lang: str = "en") -> str:
    """A short, factual brand-tier phrase for the reason sentence."""
    p = _BRAND_PHRASES.get(lang, _BRAND_PHRASES["en"])
    if prog.institute_type == "IIT":
        return p["top_iit"] if prog.brand_score >= 1.0 else p["iit"]
    if prog.institute_type == "NIT":
        return p["top_nit"] if prog.brand_score >= 0.78 else p["nit"]
    if prog.institute_type == "IIIT":
        return p["iiit"]
    return p["gfti"]


_CONFIDENCE_TAIL = {
    "en": {
        "high": "Cutoff has a wide, stable window.",
        "medium": "Cutoff has been fairly steady.",
        "fragile": "Cutoff window is tight, so treat it as volatile.",
    },
    "hi": {
        "high": "कटऑफ़ की रेंज चौड़ी और स्थिर है।",
        "medium": "कटऑफ़ काफ़ी हद तक स्थिर रहा है।",
        "fragile": "कटऑफ़ की रेंज तंग है, इसलिए इसे अस्थिर मानें।",
    },
}

# Reason-sentence fragments, keyed by language. {category} stays English (it is
# the technical Safe/Target/Reach label also used in the UI), and rank numbers
# use Western grouping ("4,000") in both languages.
_REASON_TEXT = {
    "en": {
        "clause0": "{lead} - {fit} ({branch} at {brand})",
        "lead": "{category} for you",
        "matched": "strong fit for your goal",
        "unmatched": "a sensible option to keep on your list",
        "hs": "your home-state quota gives roughly a {n:,}-rank cushion",
        "female": "the female-only seat closes about {n:,} ranks later",
        "special": "the {quota} state quota works in your favour here",
        "and": ", and ",
    },
    "hi": {
        "clause0": "{lead} – {fit} ({brand} में {branch})",
        "lead": "आपके लिए {category}",
        "matched": "आपके लक्ष्य के लिए बढ़िया विकल्प",
        "unmatched": "सूची में रखने लायक एक समझदारी भरा विकल्प",
        "hs": "आपके होम-स्टेट कोटा से लगभग {n:,} रैंक की छूट मिलती है",
        "female": "फ़ीमेल-ओनली सीट लगभग {n:,} रैंक बाद बंद होती है",
        "special": "{quota} स्टेट कोटा यहाँ आपके पक्ष में है",
        "and": ", और ",
    },
}


def _build_reason(
    prog: Program,
    category: str,
    matched: bool,
    confidence: str,
    home_state_advantage: Optional[int],
    female_seat_advantage: Optional[int],
    lang: str = "en",
) -> str:
    """Compose a one-to-two sentence, factual explanation from this row's facts."""
    t = _REASON_TEXT.get(lang, _REASON_TEXT["en"])
    clauses: List[str] = []

    lead = t["lead"].format(category=category)
    fit = t["matched"] if matched else t["unmatched"]
    clauses.append(
        t["clause0"].format(
            lead=lead, fit=fit, branch=prog.branch, brand=_brand_phrase(prog, lang)
        )
    )

    if home_state_advantage:
        clauses.append(t["hs"].format(n=home_state_advantage))
    if female_seat_advantage:
        clauses.append(t["female"].format(n=female_seat_advantage))

    quota = prog.quota
    if not home_state_advantage and quota in states.SPECIAL_QUOTA_STATE:
        clauses.append(t["special"].format(quota=quota))

    sentence = clauses[0]
    if len(clauses) > 1:
        sentence += t["and"] + t["and"].join(clauses[1:])
    tail = _CONFIDENCE_TAIL.get(lang, _CONFIDENCE_TAIL["en"])[confidence]
    return f"{sentence}. {tail}"


_NOTES = {
    "en": {
        "no_adv": (
            "No JEE Advanced rank provided, so IITs are not shown. Add an "
            "Advanced rank to include them."
        ),
        "no_mains": (
            "No JEE Mains rank provided, so NITs / IIITs / GFTIs are not shown. "
            "Add a Mains rank to include them."
        ),
        "category": (
            "Category '{cat}' is not yet supported — the current dataset "
            "contains OPEN (CRL) seats only. Results shown are for OPEN seats. "
            "Reserved-category cutoffs will be added in a future data release."
        ),
        "home_state": (
            "Home state '{state}' was not recognised, so Home-State quota seats "
            "may be missed. Pick a state from the list for accurate results."
        ),
        "branch_filter": (
            "Showing only your preferred branches ({branches}). Clear the branch "
            "filter to see every eligible option."
        ),
        "branch_filter_empty": (
            "No options matched your branch preferences ({branches}). Try adding "
            "more branches or clearing the branch filter."
        ),
    },
    "hi": {
        "no_adv": (
            "JEE Advanced रैंक नहीं दी गई, इसलिए IITs नहीं दिखाई जा रहीं। उन्हें शामिल "
            "करने के लिए Advanced रैंक डालें।"
        ),
        "no_mains": (
            "JEE Mains रैंक नहीं दी गई, इसलिए NITs / IIITs / GFTIs नहीं दिखाए जा रहे। "
            "उन्हें शामिल करने के लिए Mains रैंक डालें।"
        ),
        "category": (
            "श्रेणी '{cat}' अभी समर्थित नहीं है — मौजूदा डेटा में केवल OPEN (CRL) सीटें "
            "हैं। दिखाए गए नतीजे OPEN सीटों के लिए हैं। आरक्षित-श्रेणी के कटऑफ़ आगे "
            "जोड़े जाएँगे।"
        ),
        "home_state": (
            "होम स्टेट '{state}' पहचाना नहीं गया, इसलिए हो सकता है कुछ होम-स्टेट कोटा "
            "सीटें छूट जाएँ। सही नतीजों के लिए सूची से अपना राज्य चुनें।"
        ),
        "branch_filter": (
            "केवल आपकी पसंदीदा ब्रांच ({branches}) दिखाई जा रही हैं। हर योग्य विकल्प "
            "देखने के लिए ब्रांच फ़िल्टर हटाएँ।"
        ),
        "branch_filter_empty": (
            "आपकी ब्रांच पसंद ({branches}) से कोई विकल्प मेल नहीं खाया। और ब्रांच जोड़ें "
            "या ब्रांच फ़िल्टर हटाकर देखें।"
        ),
    },
}

# Branch-preference value -> short label, keyed by language, for note text.
_BRANCH_PREF_LABELS = {
    "en": {
        "cs_it": "CS / IT",
        "ece": "ECE",
        "ee": "Electrical",
        "math_computing": "Mathematics & Computing",
        "ai_ds": "AI / Data Science",
        "mechanical": "Mechanical",
        "civil": "Civil",
        "chemical": "Chemical",
    },
    "hi": {
        "cs_it": "CS / IT",
        "ece": "ECE",
        "ee": "Electrical",
        "math_computing": "Mathematics & Computing",
        "ai_ds": "AI / Data Science",
        "mechanical": "Mechanical",
        "civil": "Civil",
        "chemical": "Chemical",
    },
}

_GUIDANCE = {
    "en": {
        "empty": (
            "No options matched closely. Your rank may be far from this dataset's "
            "cutoffs for the chosen filters - try providing the other rank, or "
            "double-check your gender / home-state selection."
        ),
        "found": (
            "Found {total} eligible institute-branch options for your profile "
            "(showing {shown}). They are grouped into Target, Reach and Safe, and "
            "ordered to match your stated interest."
        ),
    },
    "hi": {
        "empty": (
            "कोई विकल्प क़रीब से मेल नहीं खाया। हो सकता है चुने हुए फ़िल्टर के लिए आपकी "
            "रैंक इस डेटा के कटऑफ़ से काफ़ी दूर हो — दूसरी रैंक डालकर देखें, या अपना "
            "जेंडर / होम-स्टेट चुनाव दोबारा जाँच लें।"
        ),
        "found": (
            "आपकी प्रोफ़ाइल के लिए {total} योग्य संस्थान-ब्रांच विकल्प मिले "
            "({shown} दिखाए जा रहे हैं)। इन्हें Target, Reach और Safe में बाँटा गया है "
            "और आपकी बताई रुचि के अनुसार क्रम में लगाया गया है।"
        ),
    },
}


def recommend(req: RecommendRequest) -> RecommendResponse:
    programs = load_programs()
    lang = req.lang if req.lang in ("en", "hi") else "en"
    notes_text = _NOTES.get(lang, _NOTES["en"])
    notes: List[str] = []

    if req.adv_rank is None:
        notes.append(notes_text["no_adv"])
    if req.mains_rank is None:
        notes.append(notes_text["no_mains"])
    if req.seat_category != "OPEN":
        notes.append(notes_text["category"].format(cat=req.seat_category))
    if req.home_state not in states.INDIAN_STATES:
        notes.append(notes_text["home_state"].format(state=req.home_state))

    # Branch preferences -> the set of branch tags the student wants to see.
    # An empty set means "no filter" (show every eligible branch).
    wanted_tags = states.tags_for_branch_preferences(req.branch_preferences)

    hs_index = home_state_advantage_index()
    female_index = female_seat_advantage_index()

    results: List[Recommendation] = []
    for prog in programs:
        rank = _relevant_rank(prog, req)
        if rank is None:
            continue
        if not _passes_gender(prog, req.gender):
            continue
        if not _passes_quota(prog, req.home_state):
            continue
        if wanted_tags and prog.tags.isdisjoint(wanted_tags):
            continue
        category = _categorize(rank, prog.opening_rank, prog.closing_rank)
        if category is None:
            continue
        score, matched = _interest_score(prog, req.goal)

        home_state_advantage = None
        if prog.quota == "HS":
            home_state_advantage = hs_index.get(
                (prog.institute, prog.branch_full, prog.exam, prog.gender_pool)
            )
        female_seat_advantage = None
        if req.gender == "female" and prog.gender_pool == "female":
            female_seat_advantage = female_index.get(
                (prog.institute, prog.branch_full, prog.exam, prog.quota)
            )

        confidence = _confidence(prog.opening_rank, prog.closing_rank)
        reason = _build_reason(
            prog,
            category,
            matched,
            confidence,
            home_state_advantage,
            female_seat_advantage,
            lang,
        )

        results.append(
            Recommendation(
                institute=prog.institute,
                institute_type=prog.institute_type,
                institute_state=prog.institute_state,
                exam=prog.exam,
                branch=prog.branch,
                branch_full=prog.branch_full,
                degree=prog.degree,
                quota=prog.quota,
                gender_pool=prog.gender_pool,
                opening_rank=prog.opening_rank,
                closing_rank=prog.closing_rank,
                category=category,
                fit_label=FIT_LABELS.get(lang, FIT_LABELS["en"])[category],
                interest_score=round(score, 2),
                matched_interest=matched,
                home_state_advantage=home_state_advantage,
                female_seat_advantage=female_seat_advantage,
                confidence=confidence,
                reason=reason,
            )
        )

    results.sort(
        key=lambda r: (
            CATEGORY_ORDER[r.category],
            -r.interest_score,
            r.closing_rank,
            r.institute,
            r.branch,
        )
    )

    total_found = len(results)

    # Tell the student a branch filter is shaping these results.
    if wanted_tags:
        valid_prefs = [
            p for p in req.branch_preferences if p in states.VALID_BRANCH_PREFERENCES
        ]
        pref_labels = _BRANCH_PREF_LABELS.get(lang, _BRANCH_PREF_LABELS["en"])
        branch_names = ", ".join(pref_labels.get(p, p) for p in valid_prefs)
        note_key = "branch_filter" if total_found else "branch_filter_empty"
        notes.append(notes_text[note_key].format(branches=branch_names))

    results = results[: req.max_results]

    counts = {
        "total": total_found,
        "shown": len(results),
        "by_category": {c: sum(1 for r in results if r.category == c) for c in CATEGORY_ORDER},
        "by_type": {
            t: sum(1 for r in results if r.institute_type == t)
            for t in ("IIT", "NIT", "IIIT", "GFTI")
        },
    }

    blurbs = CATEGORY_BLURBS.get(lang, CATEGORY_BLURBS["en"])
    category_guidance = [
        CategoryGuidance(
            category=c,
            count=counts["by_category"][c],
            blurb=blurbs[c],
        )
        for c in CATEGORY_ORDER
        if counts["by_category"][c] > 0
    ]

    guidance_text = _GUIDANCE.get(lang, _GUIDANCE["en"])
    if total_found == 0:
        overall = guidance_text["empty"]
    else:
        overall = guidance_text["found"].format(total=total_found, shown=len(results))

    interest_guidance = states.GOAL_GUIDANCE.get(lang, states.GOAL_GUIDANCE["en"]).get(
        req.goal, ""
    )

    return RecommendResponse(
        guidance=overall,
        interest_guidance=interest_guidance,
        counts=counts,
        notes=notes,
        category_guidance=category_guidance,
        recommendations=results,
    )
