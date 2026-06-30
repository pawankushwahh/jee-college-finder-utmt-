"""Core recommendation pipeline: take a student profile and return a filtered,
categorized and interest-ranked list of institute + branch options.
"""

from __future__ import annotations

from typing import List, Optional
import math

from . import states
from .data_loader import (
    Program,
    female_seat_advantage_index,
    home_state_advantage_index,
    load_programs,
    get_program_history,
)
from .config import settings
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
        "Reach": "महत्वाकांक्षी — पिछले साल की क्लोज़િંગ रैंक से थोड़ा आगे, पर कोशिश के लायक।",
    },
    "gu": {
        "Safe": "આરામદાયક — તમારો રેન્ક ગયા વર્ષના ઓપનિંગ રેન્ક કરતાં વધુ સારો છે.",
        "Target": "મેળવી શકાય તેવું — તમારો રેન્ક ગયા વર્ષના ઓપનિંગ અને ક્લોઝિંગ રેન્જની વચ્ચે છે.",
        "Reach": "આશાસ્પદ — ગયા વર્ષના ક્લોઝિંગ રેન્કથી થોડો આગળ, પણ પ્રયત્ન કરવા જેવો.",
    },
    "kn": {
        "Safe": "ಆರಾಮದಾಯಕ — ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಕಳೆದ ವರ್ಷದ ಓಪನಿಂಗ್ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಉತ್ತಮವಾಗಿದೆ.",
        "Target": "ಪಡೆಯಬಹುದಾದ — ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಕಳೆದ ವರ್ಷದ ಓಪನಿಂಗ್ ಮತ್ತು ಕ್ಲೋಸಿಂಗ್ ರೇಂಜ್ ನಡುವೆ ಇದೆ.",
        "Reach": "ಆಕಾಂಕ್ಷೆಯುಳ್ಳ — ಕಳೆದ ವರ್ಷದ ಕ್ಲೋಸಿಂಗ್ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಸ್ವಲ್ಪ ಮುಂದೆ ಇದೆ, ಆದರೆ ಪ್ರಯತ್ನಿಸಲು ಯೋಗ್ಯವಾಗಿದೆ.",
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
    "gu": {
        "Target": (
            "આ તમારા રેન્કની સૌથી નજીક છે (ગયા વર્ષની ઓપનિંગ-ક્લોઝિંગ રેન્જની અંદર). "
            "આ તમારા સૌથી વાસ્તવિક વિકલ્પો છે."
        ),
        "Reach": (
            "આ ગયા વર્ષે તમારા રેન્કથી થોડા ઉપર બંધ થયા હતા. કટઓફ બદલાય છે, "
            "તેથી થોડાક આશાસ્પદ વિકલ્પો તરીકે રાખો."
        ),
        "Safe": (
            "તમારો રેન્ક અહીં ગયા વર્ષના ઓપનિંગ રેન્ક કરતાં ઘણો સારો છે, "
            "તેથી આ મજબૂત બેકઅપ છે જે તમને મળવાની પૂરી સંભાવના છે."
        ),
    },
    "kn": {
        "Target": (
            "ಇವು ನಿಮ್ಮ ರ‍್ಯಾಂಕ್‌ಗೆ ಬಹಳ ಹತ್ತಿರದಲ್ಲಿವೆ (ಕಳೆದ ವರ್ಷದ ಓಪನಿಂಗ್-ಕ್ಲೋಸಿಂಗ್ ರೇಂಜ್ ಒಳಗಡೆ). "
            "ಇವು ನಿಮ್ಮ ಅತ್ಯಂತ ಸೂಕ್ತವಾದ ಆಯ್ಕೆಗಳು."
        ),
        "Reach": (
            "ಇವು ಕಳೆದ ವರ್ಷ ನಿಮ್ಮ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಸ್ವಲ್ಪ ಮೇಲೆ ಮುಚ್ಚಲ್ಪಟ್ಟಿದ್ದವು. ಕಟ್‌ಆಫ್‌ಗಳು ಬದಲಾಗುತ್ತವೆ, "
            "ಆದ್ದರಿಂದ ಕೆಲವು ಆಕಾಂಕ್ಷೆಯ ಆಯ್ಕೆಗಳಾಗಿ ಇಟ್ಟುಕೊಳ್ಳಿ."
        ),
        "Safe": (
            "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಇಲ್ಲಿ ಕಳೆದ ವರ್ಷದ ಓಪನಿಂಗ್ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಉತ್ತಮವಾಗಿದೆ, "
            "ಆದ್ದರಿಂದ ಇವು ನಿಮಗೆ ಸಿಗುವ ಸಾಧ್ಯತೆ ಹೆಚ್ಚಿರುವ ಬಲವಾದ ಬ್ಯಾಕಪ್‌ಗಳಾಗಿವೆ."
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


def _calculate_probability(rank: int, closing_rank: int, history: dict[int, int]) -> float:
    """Calculate the probability of admission (0.0 to 100.0).
    
    Uses the historical volatility (standard deviation of closing ranks) if history is available.
    Otherwise, defaults to a volatility of 8% of the closing rank.
    """
    ranks = list(history.values())
    
    if len(ranks) >= 2:
        mean_rank = sum(ranks) / len(ranks)
        variance = sum((x - mean_rank) ** 2 for x in ranks) / len(ranks)
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.08 * closing_rank
        
    # Ensure std_dev is not too small (min 5% of closing_rank or at least 10 ranks)
    min_std_dev = max(10, 0.05 * closing_rank)
    if std_dev < min_std_dev:
        std_dev = min_std_dev
        
    # Calculate Z-score (smaller rank = better, so positive means student rank is better than closing)
    z = (closing_rank - rank) / std_dev
    
    try:
        prob = 1.0 / (1.0 + math.exp(-1.7 * z))
    except OverflowError:
        prob = 1.0 if z > 0 else 0.0
        
    return round(prob * 100.0, 1)


NORTH_STATES = {"Delhi", "Haryana", "Punjab", "Himachal Pradesh", "Jammu and Kashmir", "Ladakh", "Uttarakhand", "Uttar Pradesh", "Chandigarh"}
SOUTH_STATES = {"Karnataka", "Tamil Nadu", "Telangana", "Andhra Pradesh", "Kerala", "Puducherry"}
WEST_STATES = {"Maharashtra", "Gujarat", "Goa", "Rajasthan", "Daman and Diu"}
EAST_STATES = {"West Bengal", "Bihar", "Jharkhand", "Odisha", "Chhattisgarh"}
METRO_CITIES = {"mumbai", "delhi", "bangalore", "bengaluru", "chennai", "kolkata", "hyderabad", "pune"}


def _get_region(state: str) -> str:
    if state in NORTH_STATES:
        return "north"
    if state in SOUTH_STATES:
        return "south"
    if state in WEST_STATES:
        return "west"
    if state in EAST_STATES:
        return "east"
    return "northeast"  # default for seven sisters states, Sikkim etc.


def _is_metro(institute: str, state: str) -> bool:
    inst_lower = institute.lower()
    return any(city in inst_lower for city in METRO_CITIES) or state == "Delhi"


# _calculate_fees is removed to focus exclusively on admission probability insights.
# Future-proofing: If verified fees data becomes available, re-implement fee calculation logic here.


def _interest_score(prog: Program, goal: str, ratio: float) -> tuple[float, bool]:
    weights = states.GOAL_TAG_WEIGHTS.get(goal, {})
    branch_score = max((weights.get(t, 0) for t in prog.tags), default=0)
    brand_score = prog.brand_score * 10.0
    # Blend according to the user preference slider ratio (0.0 = purely branch, 1.0 = purely brand)
    score = (1.0 - ratio) * branch_score + ratio * brand_score
    return float(score), branch_score > 0


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
    "gu": {
        "top_iit": "એક ટોચની IIT",
        "iit": "એક IIT",
        "top_nit": "એક ટોચની NIT",
        "nit": "એક NIT",
        "iiit": "એક IIIT",
        "gfti": "સરકારી અનુદાનિત સંસ્થા",
    },
    "kn": {
        "top_iit": "ಒಂದು ಉನ್ನತ IIT",
        "iit": "ಒಂದು IIT",
        "top_nit": "ಒಂದು ಉನ್ನತ NIT",
        "nit": "ಒಂದು NIT",
        "iiit": "ಒಂದು IIIT",
        "gfti": "ಸರ್ಕಾರಿ ಅನುದಾನಿತ ಸಂಸ್ಥೆ",
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
    "gu": {
        "high": "કટઓફની શ્રેણી વિશાળ અને સ્થિર છે.",
        "medium": "કટઓફ સામાન્ય રીતે સ્થિર રહ્યો છે.",
        "fragile": "કટઓફની શ્રેણી સાંકડી છે, તેથી તેને અસ્થિર માનો.",
    },
    "kn": {
        "high": "ಕಟ್‌ಆಫ್ ವ್ಯಾಪ್ತಿಯು ವಿಸ್ತಾರವಾಗಿದೆ ಮತ್ತು ಸ್ಥಿರವಾಗಿದೆ.",
        "medium": "ಕಟ್‌ಆಫ್ ಸಾಧಾರಣವಾಗಿ ಸ್ಥಿರವಾಗಿದೆ.",
        "fragile": "ಕಟ್‌ಆಫ್ ವ್ಯಾಪ್ತಿಯು ಕಿರಿದಾಗಿದೆ, ಆದ್ದರಿಂದ ಇದು ಬದಲಾಗಬಹುದು.",
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
    "gu": {
        "clause0": "{lead} – {fit} ({brand} માં {branch})",
        "lead": "તમારા માટે {category}",
        "matched": "તમારા લક્ષ્ય માટે મજબૂત ફિટ",
        "unmatched": "તમારી યાદીમાં રાખવા માટે એક સમજદાર વિકલ્પ",
        "hs": "તમારા હોમ-સ્ટેટ ક્વોટાથી આશરે {n:,} રેન્કનો ફાયદો મળે છે",
        "female": "સ્ત્રીઓ માટેની સીટ આશરે {n:,} રેન્ક પછી બંધ થાય છે",
        "special": "{quota} સ્ટેટ ક્વોટા અહીં તમારા પક્ષમાં કામ કરે છે",
        "and": ", અને ",
    },
    "kn": {
        "clause0": "{lead} – {fit} ({brand} ನಲ್ಲಿ {branch})",
        "lead": "ನಿಮಗಾಗಿ {category}",
        "matched": "ನಿಮ್ಮ ಗುರಿಗೆ ಸೂಕ್ತ ಹೊಂದಾಣಿಕೆ",
        "unmatched": "ನಿಮ್ಮ ಪಟ್ಟಿಯಲ್ಲಿ ಇಟ್ಟುಕೊಳ್ಳಲು ಸೂಕ್ತ ಆಯ್ಕೆ",
        "hs": "ನಿಮ್ಮ ತವರು ರಾಜ್ಯ ಕೋಟಾದಿಂದ ಸುಮಾರು {n:,} ರ‍್ಯಾಂಕ್ ಗಳ ಸಡಿಲಿಕೆ ಸಿಗುತ್ತದೆ",
        "female": "ಮಹಿಳಾ ಮೀಸಲು ಸೀಟು ಸುಮಾರು {n:,} ರ‍್ಯಾಂಕ್ ಗಳ ನಂತರ ಮುಚ್ಚುತ್ತದೆ",
        "special": "{quota} ರಾಜ್ಯ ಕೋಟಾ ಇಲ್ಲಿ ನಿಮಗೆ ಸಹಕಾರಿಯಾಗಿದೆ",
        "and": ", ಮತ್ತು ",
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
    "gu": {
        "no_adv": (
            "કોઈ JEE Advanced રેન્ક આપેલ નથી, તેથી IITs બતાવવામાં આવતી નથી. "
            "તેમને સામેલ કરવા માટે Advanced રેન્ક ઉમેરો."
        ),
        "no_mains": (
            "કોઈ JEE Mains રેન્ક આપેલ નથી, તેથી NITs / IIITs / GFTIs બતાવવામાં આવતી નથી. "
            "તેમને સામેલ કરવા માટે Mains રેન્ક ઉમેરો."
        ),
        "category": (
            "કેટેગરી '{cat}' હજી સપોર્ટેડ નથી — હાલના ડેટાસેટમાં ફક્ત OPEN (CRL) સીટો "
            "છે. બતાવેલ પરિણામો OPEN સીટો માટે છે. અનામત કેટેગરીના કટઓફ ભવિષ્યના ડેટા રીલીઝમાં ઉમેરવામાં આવશે."
        ),
        "home_state": (
            "હોમ સ્ટેટ '{state}' ઓળખાયું નથી, તેથી હોમ-સ્ટેટ ક્વોટા સીટો "
            "ચૂકી જવાય છે. ચોક્કસ પરિણામો માટે સૂચિમાંથી રાજ્ય પસંદ કરો."
        ),
        "branch_filter": (
            "ફક્ત તમારી પસંદગીની બ્રાન્ચો ({branches}) બતાવી રહ્યા છીએ. "
            "બધા પાત્ર વિકલ્પો જોવા માટે બ્રાન્ચ ફિલ્ટર સાફ કરો."
        ),
        "branch_filter_empty": (
            "તમારી બ્રાન્ચ પસંદગીઓ ({branches}) સાથે કોઈ વિકલ્પ મેળ ખાતો નથી. "
            "વધુ બ્રાન્ચ ઉમેરવાનો અથવા ફિલ્ટર સાફ કરવાનો પ્રયાસ કરો."
        ),
    },
    "kn": {
        "no_adv": (
            "ಯಾವುದೇ JEE Advanced ರ‍್ಯಾಂಕ್ ನಮೂದಿಸಿಲ್ಲ, ಆದ್ದರಿಂದ IITs ಗಳನ್ನು ತೋರಿಸುತ್ತಿಲ್ಲ. "
            "ಅವುಗಳನ್ನು ಸೇರಿಸಲು Advanced ರ‍್ಯಾಂಕ್ ನಮೂದಿಸಿ."
        ),
        "no_mains": (
            "ಯಾವುದೇ JEE Mains ರ‍್ಯಾಂಕ್ ನಮೂದಿಸಿಲ್ಲ, ಆದ್ದರಿಂದ NITs / IIITs / GFTIs ಗಳನ್ನು ತೋರಿಸುತ್ತಿಲ್ಲ. "
            "ಅವುಗಳನ್ನು ಸೇರಿಸಲು Mains ರ‍್ಯಾಂಕ್ ನಮೂದಿಸಿ."
        ),
        "category": (
            "ವರ್ಗ '{cat}' ಗೆ ಇನ್ನೂ ಬೆಂಬಲವಿಲ್ಲ — ಪ್ರಸ್ತುತ ಡೇಟಾಬೇಸ್ ಕೇವಲ OPEN (CRL) ಸೀಟುಗಳನ್ನು "
            "ಮಾತ್ರ ಒಳಗೊಂಡಿದೆ. ತೋರಿಸಲಾದ ಫಲಿತಾಂಶಗಳು OPEN ಸೀಟುಗಳಿಗೆ ಸಂಬಂಧಿಸಿವೆ. ಮೀಸಲಾತಿ ವರ್ಗದ ಕಟ್‌ಆಫ್‌ಗಳನ್ನು ಭವಿಷ್ಯದಲ್ಲಿ ಸೇರಿಸಲಾಗುತ್ತದೆ."
        ),
        "home_state": (
            "ತವರು ರಾಜ್ಯ '{state}' ಗುರುತಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ, ಆದ್ದರಿಂದ ತವರು ರಾಜ್ಯದ ಸೀಟುಗಳು "
            "ಕೈತಪ್ಪಿಹೋಗಬಹುದು. ನಿಖರ ಫಲಿತಾಂಶಕ್ಕಾಗಿ ಪಟ್ಟಿಯಿಂದ ರಾಜ್ಯವನ್ನು ಆರಿಸಿ."
        ),
        "branch_filter": (
            "ನಿಮ್ಮ ಆದ್ಯತೆಯ ಬ್ರಾಂಚ್‌ಗಳನ್ನು ಮಾತ್ರ ತೋರಿಸಲಾಗುತ್ತಿದೆ ({branches}). "
            "ಎಲ್ಲಾ ಅರ್ಹ ಆಯ್ಕೆಗಳನ್ನು ನೋಡಲು ಫಿಲ್ಟರ್ ಅನ್ನು ತೆರವುಗೊಳಿಸಿ."
        ),
        "branch_filter_empty": (
            "ನಿಮ್ಮ ಬ್ರಾಂಚ್ ಆದ್ಯತೆಗಳಿಗೆ ({branches}) ಯಾವುದೇ ಆಯ್ಕೆಗಳು ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ. "
            "ಹೆಚ್ಚಿನ ಬ್ರಾಂಚ್‌ಗಳನ್ನು ಸೇರಿಸಿ ಅಥವಾ ಫಿಲ್ಟರ್ ತೆರವುಗೊಳಿಸಿ."
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
    "gu": {
        "cs_it": "CS / IT",
        "ece": "ECE",
        "ee": "Electrical",
        "math_computing": "Mathematics & Computing",
        "ai_ds": "AI / Data Science",
        "mechanical": "Mechanical",
        "civil": "Civil",
        "chemical": "Chemical",
    },
    "kn": {
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
    "gu": {
        "empty": (
            "કોઈ વિકલ્પ નજીકથી મેળ ખાતો નથી. તમારો રેન્ક પસંદ કરેલા ફિલ્ટર્સ માટે આ ડેટાસેટના "
            "કટઓફથી ઘણો દૂર હોઈ શકે છે - બીજો રેન્ક દાખલ કરવાનો પ્રયાસ કરો અથવા તમારી જાતિ / હોમ-સ્ટેટની પસંદગી તપાસો."
        ),
        "found": (
            "તમારી પ્રોફાઇલ માટે {total} પાત્ર સંસ્થા-બ્રાન્ચ વિકલ્પો મળ્યા "
            "({shown} બતાવી રહ્યા છીએ). તેઓ Target, Reach અને Safe માં વર્ગીકૃત થયેલ છે "
            "અને તમારી જણાવેલી રુચિ અનુસાર ગોઠવાયેલા છે."
        ),
    },
    "kn": {
        "empty": (
            "ಯಾವುದೇ ಆಯ್ಕೆಗಳು ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ. ಆಯ್ದ ಫಿಲ್ಟರ್‌ಗಳಿಗೆ ಈ ಡೇಟಾಬೇಸ್‌ನಲ್ಲಿ ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ "
            "ಬಹಳ ದೂರವಿರಬಹುದು - ಇನ್ನೊಂದು ರ‍್ಯಾಂಕ್ ನಮೂದಿಸಿ ಅಥವಾ ನಿಮ್ಮ ಲಿಂಗ / ತವರು ರಾಜ್ಯದ ಆಯ್ಕೆಯನ್ನು ಮತ್ತೊಮ್ಮೆ ಪರಿಶೀಲಿಸಿ."
        ),
        "found": (
            "ನಿಮ್ಮ ಪ್ರೊಫೈಲ್‌ಗೆ ಹೊಂದುವ {total} ಕಾಲೇಜು-ಬ್ರಾಂಚ್ ಆಯ್ಕೆಗಳು ಕಂಡುಬಂದಿವೆ "
            "({shown} ತೋರಿಸಲಾಗುತ್ತಿದೆ). ಇವುಗಳನ್ನು Target, Reach ಮತ್ತು Safe ಎಂದು ವರ್ಗೀಕರಿಸಿ, "
            "ನಿಮ್ಮ ಆಸಕ್ತಿಗೆ ತಕ್ಕಂತೆ ಜೋಡಿಸಲಾಗಿದೆ."
        ),
    },
}


def recommend(req: RecommendRequest) -> RecommendResponse:
    # Resolve effective data_mode: server can lock it regardless of what the
    # client sends when allow_user_data_toggle is False.
    effective_mode = req.data_mode if settings.allow_user_data_toggle else settings.data_mode

    programs = load_programs(effective_mode)
    lang = req.lang if req.lang in ("en", "hi", "gu", "kn") else "en"
    notes_text = _NOTES.get(lang, _NOTES["en"])
    notes: List[str] = []

    if req.adv_rank is None:
        notes.append(notes_text["no_adv"])
    if req.mains_rank is None:
        notes.append(notes_text["no_mains"])
    # Only warn about unsupported category in basic mode (extended supports all).
    if req.seat_category != "OPEN" and effective_mode == "basic":
        notes.append(notes_text["category"].format(cat=req.seat_category))
    if req.home_state not in states.INDIAN_STATES:
        notes.append(notes_text["home_state"].format(state=req.home_state))

    # Branch preferences -> the set of branch tags the student wants to see.
    # An empty set means "no filter" (show every eligible branch).
    wanted_tags = states.tags_for_branch_preferences(req.branch_preferences)

    hs_index = home_state_advantage_index(effective_mode)
    female_index = female_seat_advantage_index(effective_mode)

    # In extended mode, filter programs to the requested seat_category.
    # In basic mode, all programs are OPEN — no filtering needed.
    seat_filter = req.seat_category if effective_mode == "extended" else None

    results: List[Recommendation] = []
    for prog in programs:
        rank = _relevant_rank(prog, req)
        if rank is None:
            continue
        # In extended mode, filter by seat_type (OPEN / OBC-NCL / SC / ST / EWS / PwD)
        if seat_filter and prog.seat_type != seat_filter:
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
        score, matched = _interest_score(prog, req.goal, req.brand_branch_ratio)

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

        # Fee calculation is removed to focus on admission probability insights.
        # Future-proofing: If verified fees data becomes available, recalculate est_fees, waiver_applied, and fee_note here.
        region = _get_region(prog.institute_state)
        is_metro = _is_metro(prog.institute, prog.institute_state)

        history = get_program_history(prog, effective_mode)
        prob = _calculate_probability(rank, prog.closing_rank, history)

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
                # estimated_fees, fee_waiver_applied, fee_note are removed to focus on admission insights.
                # Future-proofing: If verified fees data becomes available, pass these fields:
                # estimated_fees=est_fees,
                # fee_waiver_applied=waiver_applied,
                # fee_note=fee_note,
                region=region,
                is_metro=is_metro,
                history=history,
                admission_probability=prob,
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
