"""COMEDK recommendation engine — the same pipeline every exam here runs.

Pipeline:  filter → categorise → score → explain → order → curate.

A maintainer who knows the JEE engine (``app/disha/recommender.py``) or the
KCET one should be able to read this file and recognise every stage. The stage
*rules* — bucket ordering, the institute-diversity cap, top-rank detection, the
point-cutoff maths — come from ``app/disha/core/``, so COMEDK and KCET cannot
drift apart on what they mean. What stays here is what COMEDK's own counselling
rules require; ``docs/EXAM_DIFFERENCES.md`` inventories the full set.

What JEE actually does, and why it works
---------------------------------------
JoSAA publishes an opening **and** a closing rank, so JEE can ask a factual
question per programme: "did a student at your rank get a seat here last year?"
Target means the rank lands inside that observed window, Safe means it beats the
window, Reach means it is just past the closing rank.  JEE then keeps the answer
useful in two further ways that matter as much as the buckets themselves: it
prunes options the student is grossly overqualified for, and for top rankers —
where that prune would leave nothing — it falls back to "the ten most
competitive programmes you are eligible for".

The output is always a shortlist, never the whole table.  That is the idea this
engine reproduces, using the one cutoff COMEDK gives us.

Key structural differences from JEE (all intentional):

* **Single cutoff, no opening rank.**  COMEDK publishes one rank per programme
  — the closing rank of the last admitted candidate — so the admitted window is
  unobserved and has to be modelled.  It is modelled as a band below the cutoff
  whose width is a fraction of the cutoff **clamped into an absolute range**
  (see ``config.py`` for the numbers and the reasoning).  A pure fraction, which
  this engine used previously, means 104 ranks at a cutoff of 692 but 16,770 at
  a cutoff of 111,800 — so every option collapsed into Safe for good ranks,
  Target held 100 programmes for weak ones, and no Safe option existed at all
  above rank 95,030.

* **Curation by ordering and capping, never by deletion.**  JEE prunes with a
  lower-bound margin (rank < opening × 0.35).  That is correct for JoSAA's
  ~12,000 rows across 118 institutes.  It is **wrong** for COMEDK's 637 rows —
  it is the cause of Bug 1 (a rank-500 student seeing 37 instead of 459
  programmes).  So there is still no lower-bound prune here and there must not
  be one: ``LOWER_MARGIN`` has no place in this module.  Instead each bucket is
  ordered best-first and then capped for display, which reaches the same goal as
  JEE's prune — a shortlist of the best options rather than the entire eligible
  table — while keeping every eligible programme counted and reachable.  A
  rank-2,000 student sees the eight strongest backups (cutoffs 3,030–7,819)
  instead of a 449-row walk down to cutoff 111,800, and the response still
  reports all 449.

* **Institute diversity is enforced.**  Quality ordering alone gave a rank-1
  student six of ten cards from one college.  At most
  ``settings.max_per_institute`` programmes per institute appear in a bucket,
  relaxed when a bucket cannot otherwise fill.

* **No volatility metric.**  COMEDK has one round, so there is no spread to
  measure.  Confidence is derived from rank headroom alone.

* **Institute tiers are data-derived, not hand-written.**  Computed in
  ``data_loader.py`` from median GM cutoff, and used only as a mild prior
  alongside each programme's own cutoff percentile.

* **Branch families never reorder, they only filter.**  The ``branch_families``
  request field is an explicit opt-in filter for students who want to narrow the
  list; ordering is by option quality alone.

Key differences from KCET (also intentional — same approach, different exam):

* **A modelled band, not an observed range.**  Both exams publish per-round
  cut-offs, but COMEDK's rounds are not category-symmetric (GM ran in rounds
  1/3/4, KKR in 1/2), so a "range across the rounds" would mean different things
  in the two quotas.  COMEDK collapses to one cut-off and models the band around
  it; KCET reads the range off rounds that are near-symmetric across its 48
  category codes (47 publish all three).
* **A dynamic target-band floor** (``dynamic_floor_fraction = 0.5``).  At a
  cutoff of 692 a flat 1,000-rank floor would swallow the whole rank range below
  it and stop top ranks reading as Safe.  KCET's cut-offs start an order of
  magnitude higher, so it uses a flat floor.
* **Three confidence values**, adding ``borderline`` for the coin-flip zone.
  KCET has two.  Same field name, different question — a shared vocabulary would
  force one of them to lie.
* **A hard rank gate on top-rank mode** (rank <= 100), and top-rank mode wins
  over a single-bucket request.  KCET detects from bucket counts alone and lets
  the request win.
* **Four languages** (en/hi/gu/kn) and **paginated results**.  KCET's response is
  English-only and unpaginated.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set



from ..core import curation
from ..core.cutoff import PointCutoffModel
from .config import settings
from .data_loader import get_programs
from .schemas import (
    ComedkCategoryGuidance,
    ComedkProgramNode,
    ComedkRecommendRequest,
    ComedkRecommendResponse,
)
from . import states

# ═══════════════════════════════════════════════════════════════════════════
# Constants — keep JEE's exact values where stated
# ═══════════════════════════════════════════════════════════════════════════

# Keep JEE's exact UPPER_MARGIN so "Reach" means the same thing across exams.
UPPER_MARGIN = 0.25
SAFE_MARGIN = 0.15

# Absolute clamps on the two bands.  See config.py for why a pure fraction of a
# single cutoff cannot carry one meaning across a 692 → 111,800 rank range.
TARGET_BAND_FLOOR = settings.target_band_floor
TARGET_BAND_CEILING = settings.target_band_ceiling
REACH_BAND_CEILING = settings.reach_band_ceiling

# Display order — shared with every exam.
CATEGORY_ORDER = curation.BUCKET_ORDER

# Probability curve constants.
# SIGMA_FRACTION is a *stated prior, not a fitted value*.  Only one year of
# COMEDK data exists in this repo, so it cannot be estimated from year-over-year
# cutoff movement.  A second year of cutoffs would let it be fitted per branch
# family.  0.12 is a reasonable assumption: year-over-year drift is roughly
# proportional to where the cutoff sits (a cutoff near 700 moves by tens of
# ranks; one near 90,000 moves by thousands).
SIGMA_FRACTION = settings.sigma_fraction
SIGMA_FLOOR = settings.sigma_floor
SIGMA_CEILING = settings.sigma_ceiling
STEEPNESS = settings.steepness  # same constant as JEE

# Bucket caps — used to curate the combined list so that it is not overwhelming.
# For normal ranks, we cap the number of cards shown per bucket to sum to ~60.
BUCKET_CAPS = {
    "Target": settings.cap_target,
    "Reach": settings.cap_reach,
    "Safe": settings.cap_safe,
}

# Max programmes from one institute inside a single bucket's shown list.
# Used only in the top-rank fallback curated view.
MAX_PER_INSTITUTE = settings.max_per_institute

# Top-rank fallback: for ranks ≤ this threshold, all programmes are Safe and
# the three-bucket framing provides no signal.  Show the top N most competitive
# programmes instead — mirroring JEE's _apply_top_rank_fallback().
TOP_RANK_THRESHOLD = settings.top_rank_threshold
TOP_RANK_CAP = settings.top_rank_cap

# Quality-score blend weights (programme cutoff percentile vs institute brand).
W_COMPETITIVENESS = settings.weight_competitiveness
W_BRAND = settings.weight_brand


# ═══════════════════════════════════════════════════════════════════════════
# i18n tables — inline, matching JEE's convention
# ═══════════════════════════════════════════════════════════════════════════

FIT_LABELS = {
    "en": {
        "Safe": "Comfortable — your rank is well within this programme's cutoff.",
        "Target": "Achievable — your rank is inside the range that secured a seat here last year.",
        "Reach": "Ambitious — your rank is just beyond this programme's cutoff, but worth listing.",
    },
    "hi": {
        "Safe": "आरामदायक — आपकी रैंक इस प्रोग्राम के कटऑफ़ से काफ़ी अंदर है।",
        "Target": "हासिल करने लायक — आपकी रैंक उस दायरे में है जहाँ से पिछले साल यहाँ सीट मिली थी।",
        "Reach": "महत्वाकांक्षी — आपकी रैंक कटऑफ़ से थोड़ी आगे है, पर सूची में रखने लायक।",
    },
    "gu": {
        "Safe": "આરામદાયક — તમારો રેન્ક આ પ્રોગ્રામના કટઓફ કરતાં ઘણો સારો છે.",
        "Target": "મેળવી શકાય તેવું — તમારો રેન્ક એ શ્રેણીમાં છે જ્યાંથી ગયા વર્ષે અહીં સીટ મળી હતી.",
        "Reach": "આશાસ્પદ — તમારો રેન્ક કટઓફથી થોડો આગળ છે, પણ યાદીમાં રાખવા જેવું.",
    },
    "kn": {
        "Safe": "ಆರಾಮದಾಯಕ — ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಈ ಕಾರ್ಯಕ್ರಮದ ಕಟ್‌ಆಫ್‌ಗಿಂತ ಉತ್ತಮವಾಗಿದೆ.",
        "Target": "ಪಡೆಯಬಹುದಾದ — ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಕಳೆದ ವರ್ಷ ಇಲ್ಲಿ ಸೀಟು ಸಿಕ್ಕ ವ್ಯಾಪ್ತಿಯೊಳಗಿದೆ.",
        "Reach": "ಆಕಾಂಕ್ಷೆಯುಳ್ಳ — ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಕಟ್‌ಆಫ್‌ಗಿಂತ ಸ್ವಲ್ಪ ಮುಂದೆ ಇದೆ, ಆದರೂ ಪಟ್ಟಿಯಲ್ಲಿಡಲು ಯೋಗ್ಯ.",
    },
}

CATEGORY_BLURBS = {
    "en": {
        "Target": (
            "These programmes have cutoffs close to your rank. "
            "They are your most realistic picks."
        ),
        "Reach": (
            "These closed slightly above your rank last year. Cutoffs fluctuate, "
            "so list a few as ambitious choices."
        ),
        "Safe": (
            "Your rank comfortably beats the cutoff here, so these are strong "
            "backups you are very likely to get."
        ),
    },
    "hi": {
        "Target": (
            "इन प्रोग्रामों के कटऑफ़ आपकी रैंक के करीब हैं। "
            "ये आपके सबसे realistic विकल्प हैं।"
        ),
        "Reach": (
            "ये पिछले साल आपकी रैंक से थोड़ा ऊपर बंद हुए थे। कटऑफ़ बदलते रहते हैं, "
            "इसलिए कुछ को महत्वाकांक्षी विकल्प के तौर पर रखें।"
        ),
        "Safe": (
            "आपकी रैंक यहाँ कटऑफ़ से आराम से बेहतर है, इसलिए ये मज़बूत "
            "बैकअप हैं जो आपको मिलने की पूरी संभावना है।"
        ),
    },
    "gu": {
        "Target": (
            "આ પ્રોગ્રામ્સના કટઓફ તમારા રેન્કની નજીક છે. "
            "આ તમારા સૌથી વાસ્તવિક વિકલ્પો છે."
        ),
        "Reach": (
            "આ ગયા વર્ષે તમારા રેન્કથી થોડા ઉપર બંધ થયા હતા. કટઓફ બદલાય છે, "
            "તેથી થોડાક આશાસ્પદ વિકલ્પો તરીકે રાખો."
        ),
        "Safe": (
            "તમારો રેન્ક અહીં કટઓફ કરતાં ઘણો સારો છે, "
            "તેથી આ મજબૂત બેકઅપ છે જે તમને મળવાની પૂરી સંભાવના છે."
        ),
    },
    "kn": {
        "Target": (
            "ಈ ಕಾರ್ಯಕ್ರಮಗಳ ಕಟ್‌ಆಫ್ ನಿಮ್ಮ ರ‍್ಯಾಂಕ್‌ಗೆ ಹತ್ತಿರದಲ್ಲಿವೆ. "
            "ಇವು ನಿಮ್ಮ ಅತ್ಯಂತ ಸೂಕ್ತವಾದ ಆಯ್ಕೆಗಳು."
        ),
        "Reach": (
            "ಇವು ಕಳೆದ ವರ್ಷ ನಿಮ್ಮ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಸ್ವಲ್ಪ ಮೇಲೆ ಮುಚ್ಚಲ್ಪಟ್ಟಿದ್ದವು. "
            "ಕಟ್‌ಆಫ್‌ಗಳು ಬದಲಾಗುತ್ತವೆ, ಆದ್ದರಿಂದ ಕೆಲವು ಆಕಾಂಕ್ಷೆಯ ಆಯ್ಕೆಗಳಾಗಿ ಇಟ್ಟುಕೊಳ್ಳಿ."
        ),
        "Safe": (
            "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಇಲ್ಲಿ ಕಟ್‌ಆಫ್‌ಗಿಂತ ಉತ್ತಮವಾಗಿದೆ, "
            "ಆದ್ದರಿಂದ ಇವು ನಿಮಗೆ ಸಿಗುವ ಸಾಧ್ಯತೆ ಹೆಚ್ಚಿರುವ ಬಲವಾದ ಬ್ಯಾಕಪ್‌ಗಳಾಗಿವೆ."
        ),
    },
}

_BRAND_PHRASES = {
    "en": {
        "elite": "an elite-tier college",
        "top": "a top-tier college",
        "strong": "a strong college",
        "mid": "a mid-tier college",
        "emerging": "an emerging college",
    },
    "hi": {
        "elite": "एक शीर्ष-स्तरीय कॉलेज",
        "top": "एक उच्च-स्तरीय कॉलेज",
        "strong": "एक मज़बूत कॉलेज",
        "mid": "एक मध्यम-स्तरीय कॉलेज",
        "emerging": "एक उभरता कॉलेज",
    },
    "gu": {
        "elite": "એક ટોચની કોલેજ",
        "top": "એક ઉચ્ચ-સ્તરની કોલેજ",
        "strong": "એક મજબૂત કોલેજ",
        "mid": "એક મધ્યમ-સ્તરની કોલેજ",
        "emerging": "એક ઉભરતી કોલેજ",
    },
    "kn": {
        "elite": "ಒಂದು ಅತ್ಯುತ್ತಮ ಕಾಲೇಜು",
        "top": "ಒಂದು ಉನ್ನತ ಕಾಲೇಜು",
        "strong": "ಒಂದು ಬಲವಾದ ಕಾಲೇಜು",
        "mid": "ಒಂದು ಮಧ್ಯಮ ಶ್ರೇಣಿಯ ಕಾಲೇಜು",
        "emerging": "ಒಂದು ಉದಯೋನ್ಮುಖ ಕಾಲೇಜು",
    },
}

_CONFIDENCE_TAIL = {
    "en": {
        "high": "You have significant headroom above this cutoff.",
        "medium": "You are within a reasonable margin of this cutoff.",
        "borderline": "Your rank is very close to this cutoff — treat as volatile.",
    },
    "hi": {
        "high": "इस कटऑफ़ से आपको काफ़ी मार्जिन मिला है।",
        "medium": "आप इस कटऑफ़ के उचित मार्जिन में हैं।",
        "borderline": "आपकी रैंक इस कटऑफ़ के बहुत करीब है — इसे अस्थिर मानें।",
    },
    "gu": {
        "high": "આ કટઓફ કરતાં તમને ઘણો માર્જિન મળ્યો છે.",
        "medium": "તમે આ કટઓફના વાજબી માર્જિનમાં છો.",
        "borderline": "તમારો રેન્ક આ કટઓફની ખૂબ નજીક છે — અસ્થિર ગણો.",
    },
    "kn": {
        "high": "ಈ ಕಟ್‌ಆಫ್‌ಗಿಂತ ನಿಮಗೆ ಸಾಕಷ್ಟು ಹೆಡ್‌ರೂಮ್ ಇದೆ.",
        "medium": "ನೀವು ಈ ಕಟ್‌ಆಫ್‌ನ ಸಮಂಜಸ ಅಂತರದಲ್ಲಿದ್ದೀರಿ.",
        "borderline": "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಈ ಕಟ್‌ಆಫ್‌ಗೆ ಬಹಳ ಹತ್ತಿರದಲ್ಲಿದೆ — ಅಸ್ಥಿರ ಎಂದು ಪರಿಗಣಿಸಿ.",
    },
}

_REASON_TEXT = {
    "en": {
        "clause0": "{lead} — {fit} ({branch} at {brand})",
        "lead": "{category} for you",
        "matched": "strong fit for your goal",
        "unmatched": "a sensible option to keep on your list",
        "kkr_positive": "KKR pool gives roughly a {n:,}-rank cushion here",
        "kkr_negative": "the KKR pool closed {n:,} ranks earlier than GM here",
        "and": ", and ",
    },
    "hi": {
        "clause0": "{lead} — {fit} ({brand} में {branch})",
        "lead": "आपके लिए {category}",
        "matched": "आपके लक्ष्य के लिए बढ़िया विकल्प",
        "unmatched": "सूची में रखने लायक एक समझदारी भरा विकल्प",
        "kkr_positive": "KKR पूल से यहाँ लगभग {n:,} रैंक की छूट मिलती है",
        "kkr_negative": "KKR पूल यहाँ GM से {n:,} रैंक पहले बंद हुआ है",
        "and": ", और ",
    },
    "gu": {
        "clause0": "{lead} — {fit} ({brand} માં {branch})",
        "lead": "તમારા માટે {category}",
        "matched": "તમારા લક્ષ્ય માટે મજબૂત ફિટ",
        "unmatched": "તમારી યાદીમાં રાખવા માટે એક સમજદાર વિકલ્પ",
        "kkr_positive": "KKR પૂલ અહીં આશરે {n:,} રેન્કનો ફાયદો આપે છે",
        "kkr_negative": "KKR પૂલ અહીં GM કરતાં {n:,} રેન્ક પહેલાં બંધ થયો છે",
        "and": ", અને ",
    },
    "kn": {
        "clause0": "{lead} — {fit} ({brand} ನಲ್ಲಿ {branch})",
        "lead": "ನಿಮಗಾಗಿ {category}",
        "matched": "ನಿಮ್ಮ ಗುರಿಗೆ ಸೂಕ್ತ ಹೊಂದಾಣಿಕೆ",
        "unmatched": "ನಿಮ್ಮ ಪಟ್ಟಿಯಲ್ಲಿ ಇಟ್ಟುಕೊಳ್ಳಲು ಸೂಕ್ತ ಆಯ್ಕೆ",
        "kkr_positive": "KKR ಪೂಲ್ ಇಲ್ಲಿ ಸುಮಾರು {n:,} ರ‍್ಯಾಂಕ್‌ಗಳ ಸಡಿಲಿಕೆ ನೀಡುತ್ತದೆ",
        "kkr_negative": "KKR ಪೂಲ್ ಇಲ್ಲಿ GM ಗಿಂತ {n:,} ರ‍್ಯಾಂಕ್‌ಗಳ ಮೊದಲು ಮುಚ್ಚಲ್ಪಟ್ಟಿದೆ",
        "and": ", ಮತ್ತು ",
    },
}

_GUIDANCE = {
    "en": {
        "empty": (
            "No options matched for your rank and filters. Your rank may be "
            "beyond the published cutoffs for this quota. Try a different quota "
            "or double-check your rank."
        ),
        "found": (
            "Found {total} eligible programme options for your COMEDK profile "
            "(showing {shown}). They are grouped into Target, Reach and Safe, "
            "and ordered to match your stated interest."
        ),
        "beyond_data": (
            "Your rank ({rank:,}) is past the highest published cutoff "
            "({max_cutoff:,}) in this quota. The options shown are within the "
            "historical fluctuation margin and should be treated as speculative."
        ),
        "no_results_beyond": (
            "Your rank ({rank:,}) is well past the highest published cutoff "
            "({max_cutoff:,}) in this quota. No programmes fall within a "
            "realistic admission range. Consider applying to other exams or "
            "exploring management-quota seats."
        ),
        "rank_implausible": (
            "A rank of {rank:,} is outside COMEDK's plausible rank range (ranks "
            "are accepted up to {max_rank:,}), so this looks like a typo. Please "
            "check the rank printed on your result card."
        ),
    },
    "hi": {
        "empty": (
            "आपकी रैंक और फ़िल्टर के लिए कोई विकल्प मेल नहीं खाया। आपकी रैंक "
            "इस कोटा के प्रकाशित कटऑफ़ से आगे हो सकती है।"
        ),
        "found": (
            "आपकी COMEDK प्रोफ़ाइल के लिए {total} योग्य प्रोग्राम विकल्प मिले "
            "({shown} दिखाए जा रहे हैं)। इन्हें Target, Reach और Safe में बाँटा "
            "गया है और आपकी बताई रुचि के अनुसार क्रम में लगाया गया है।"
        ),
        "beyond_data": (
            "आपकी रैंक ({rank:,}) इस कोटा के सबसे ऊँचे प्रकाशित कटऑफ़ ({max_cutoff:,}) "
            "से आगे है। दिखाए गए विकल्प ऐतिहासिक उतार-चढ़ाव के मार्जिन में हैं और "
            "इन्हें अनुमानित मानें।"
        ),
        "no_results_beyond": (
            "आपकी रैंक ({rank:,}) इस कोटा के सबसे ऊँचे कटऑफ़ ({max_cutoff:,}) से "
            "काफ़ी आगे है। किसी भी प्रोग्राम में वास्तविक प्रवेश संभावना नहीं है।"
        ),
        "rank_implausible": (
            "{rank:,} रैंक COMEDK की संभावित रैंक सीमा से बाहर है (यहाँ {max_rank:,} तक "
            "की रैंक स्वीकार की जाती है), इसलिए यह टाइपिंग की गलती लगती है। कृपया अपने "
            "रिज़ल्ट कार्ड पर छपी रैंक जाँच लें।"
        ),
    },
    "gu": {
        "empty": (
            "તમારા રેન્ક અને ફિલ્ટર્સ માટે કોઈ વિકલ્પ મેળ ખાતો નથી. તમારો રેન્ક "
            "આ ક્વોટાના પ્રકાશિત કટઓફથી આગળ હોઈ શકે છે."
        ),
        "found": (
            "તમારી COMEDK પ્રોફાઇલ માટે {total} પાત્ર પ્રોગ્રામ વિકલ્પો મળ્યા "
            "({shown} બતાવી રહ્યા છીએ). તેઓ Target, Reach અને Safe માં "
            "વર્ગીકૃત થયેલ છે."
        ),
        "beyond_data": (
            "તમારો રેન્ક ({rank:,}) આ ક્વોટાના સૌથી ઊંચા પ્રકાશિત કટઓફ ({max_cutoff:,}) "
            "થી આગળ છે. બતાવેલ વિકલ્પો ઐતિહાસિક વધઘટ માર્જિનમાં છે."
        ),
        "no_results_beyond": (
            "તમારો રેન્ક ({rank:,}) આ ક્વોટાના સૌથી ઊંચા કટઓફ ({max_cutoff:,}) થી "
            "ઘણો આગળ છે. કોઈ પ્રોગ્રામમાં વાસ્તવિક પ્રવેશ સંભાવના નથી."
        ),
        "rank_implausible": (
            "{rank:,} રેન્ક COMEDKની સંભવિત રેન્ક શ્રેણીની બહાર છે ({max_rank:,} સુધીના "
            "રેન્ક સ્વીકારાય છે), તેથી આ ટાઇપિંગની ભૂલ લાગે છે. કૃપા કરીને તમારા રિઝલ્ટ "
            "કાર્ડ પર છપાયેલો રેન્ક તપાસો."
        ),
    },
    "kn": {
        "empty": (
            "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಮತ್ತು ಫಿಲ್ಟರ್‌ಗಳಿಗೆ ಯಾವುದೇ ಆಯ್ಕೆಗಳು ಹೊಂದಿಕೆಯಾಗಲಿಲ್ಲ. "
            "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಈ ಕೋಟಾದ ಪ್ರಕಟಿತ ಕಟ್‌ಆಫ್‌ಗಳಿಗಿಂತ ಮುಂದಿರಬಹುದು."
        ),
        "found": (
            "ನಿಮ್ಮ COMEDK ಪ್ರೊಫೈಲ್‌ಗೆ {total} ಅರ್ಹ ಕಾರ್ಯಕ್ರಮ ಆಯ್ಕೆಗಳು ಕಂಡುಬಂದಿವೆ "
            "({shown} ತೋರಿಸಲಾಗುತ್ತಿದೆ). ಇವುಗಳನ್ನು Target, Reach ಮತ್ತು Safe ಎಂದು "
            "ವರ್ಗೀಕರಿಸಿ ನಿಮ್ಮ ಆಸಕ್ತಿಗೆ ತಕ್ಕಂತೆ ಜೋಡಿಸಲಾಗಿದೆ."
        ),
        "beyond_data": (
            "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ({rank:,}) ಈ ಕೋಟಾದ ಅತ್ಯಧಿಕ ಪ್ರಕಟಿತ ಕಟ್‌ಆಫ್ ({max_cutoff:,}) "
            "ಗಿಂತ ಮುಂದಿದೆ. ತೋರಿಸಲಾದ ಆಯ್ಕೆಗಳು ಐತಿಹಾಸಿಕ ಏರಿಳಿತದ ಅಂತರದಲ್ಲಿವೆ."
        ),
        "no_results_beyond": (
            "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ({rank:,}) ಈ ಕೋಟಾದ ಅತ್ಯಧಿಕ ಕಟ್‌ಆಫ್ ({max_cutoff:,}) ಗಿಂತ "
            "ಬಹಳ ಮುಂದಿದೆ. ಯಾವುದೇ ಕಾರ್ಯಕ್ರಮದಲ್ಲಿ ವಾಸ್ತವಿಕ ಪ್ರವೇಶ ಸಾಧ್ಯತೆ ಇಲ್ಲ."
        ),
        "rank_implausible": (
            "{rank:,} ರ‍್ಯಾಂಕ್ COMEDK ನ ಸಂಭಾವ್ಯ ರ‍್ಯಾಂಕ್ ವ್ಯಾಪ್ತಿಯ ಹೊರಗಿದೆ ({max_rank:,} "
            "ವರೆಗಿನ ರ‍್ಯಾಂಕ್‌ಗಳನ್ನು ಸ್ವೀಕರಿಸಲಾಗುತ್ತದೆ), ಆದ್ದರಿಂದ ಇದು ಟೈಪಿಂಗ್ ದೋಷವಿರಬಹುದು. "
            "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಫಲಿತಾಂಶ ಕಾರ್ಡ್‌ನಲ್ಲಿ ಮುದ್ರಿತ ರ‍್ಯಾಂಕ್ ಪರಿಶೀಲಿಸಿ."
        ),
    },
}

_NOTES = {
    "en": {
        "pure_science": (
            "COMEDK admits only to B.E./B.Tech programmes — there is no B.Sc. "
            "pathway through this exam. The results below are ranked towards "
            "science-adjacent engineering branches (Biotechnology, Biomedical, "
            "Chemical) that may suit your interest."
        ),
        "kkr_not_easier": (
            "Note: a KKR seat is not automatically easier to get. In most "
            "programmes the KKR pool closes earlier (at a lower numerical rank) "
            "than GM. Check the KKR gap on each card."
        ),
        "branch_filter": (
            "Showing only your preferred branches ({branches}). Clear the branch "
            "filter to see every eligible option."
        ),
        "branch_filter_empty": (
            "No options matched your branch preferences ({branches}). Try adding "
            "more branches or clearing the branch filter."
        ),
        "all_safe": (
            "Your rank clears every published cutoff in this quota, so every "
            "programme is within reach. The list below is the most competitive "
            "ones — the strongest colleges your rank can command."
        ),
        "no_safe": (
            "No programme in this quota closed far enough beyond your rank to "
            "count as a safe backup. Everything listed is a Target or a Dream, so "
            "keep other exams and management-quota seats open as a fallback."
        ),
        "curated": (
            "Showing the strongest {shown} of {total} options you are eligible "
            "for, best first, with at most {per} programmes per college."
        ),
    },
    "hi": {
        "pure_science": (
            "COMEDK केवल B.E./B.Tech प्रोग्रामों में प्रवेश देता है — इस परीक्षा "
            "से B.Sc. का रास्ता नहीं है। नीचे के नतीजे विज्ञान-संबंधी इंजीनियरिंग "
            "ब्रांच (Biotechnology, Biomedical, Chemical) के अनुसार क्रमित हैं।"
        ),
        "kkr_not_easier": (
            "ध्यान दें: KKR सीट अपने-आप आसान नहीं होती। अधिकतर प्रोग्रामों में KKR "
            "पूल GM से पहले बंद होता है। हर कार्ड पर KKR gap देखें।"
        ),
        "branch_filter": (
            "केवल आपकी पसंदीदा ब्रांच ({branches}) दिखाई जा रही हैं। सभी विकल्प "
            "देखने के लिए ब्रांच फ़िल्टर हटाएँ।"
        ),
        "branch_filter_empty": (
            "आपकी ब्रांच पसंद ({branches}) से कोई विकल्प मेल नहीं खाया। और ब्रांच जोड़ें "
            "या ब्रांच फ़िल्टर हटाकर देखें।"
        ),
        "all_safe": (
            "आपकी रैंक इस कोटा के सभी प्रकाशित कटऑफ़ से बेहतर है, इसलिए हर प्रोग्राम "
            "आपकी पहुँच में है। नीचे सबसे प्रतिस्पर्धी विकल्प दिए गए हैं — वे कॉलेज जो "
            "आपकी रैंक पर सबसे अच्छे हैं।"
        ),
        "no_safe": (
            "इस कोटा में कोई प्रोग्राम आपकी रैंक से इतना आगे बंद नहीं हुआ कि उसे सुरक्षित "
            "बैकअप माना जाए। नीचे जो है वह Target या Dream है, इसलिए दूसरी परीक्षाओं और "
            "मैनेजमेंट कोटा को विकल्प के रूप में खुला रखें।"
        ),
        "curated": (
            "आप जिन {total} विकल्पों के योग्य हैं, उनमें से सबसे मज़बूत {shown} दिखाए जा "
            "रहे हैं — बेहतर पहले, और हर कॉलेज से अधिकतम {per} प्रोग्राम।"
        ),
    },
    "gu": {
        "pure_science": (
            "COMEDK ફક્ત B.E./B.Tech પ્રોગ્રામ્સમાં પ્રવેશ આપે છે — આ પરીક્ષા "
            "દ્વારા B.Sc.નો માર્ગ નથી. નીચેના પરિણામો વિજ્ઞાન-સંબંધિત ઇજનેરી "
            "બ્રાન્ચ (Biotechnology, Biomedical, Chemical) તરફ ક્રમિત છે."
        ),
        "kkr_not_easier": (
            "નોંધ: KKR સીટ આપોઆપ સરળ નથી. મોટાભાગના પ્રોગ્રામ્સમાં KKR પૂલ "
            "GM કરતાં પહેલાં બંધ થાય છે. દરેક કાર્ડ પર KKR gap તપાસો."
        ),
        "branch_filter": (
            "ફક્ત તમારી પસંદગીની બ્રાન્ચો ({branches}) બતાવી રહ્યા છીએ. "
            "બધા વિકલ્પો જોવા માટે બ્રાન્ચ ફિલ્ટર સાફ કરો."
        ),
        "branch_filter_empty": (
            "તમારી બ્રાન્ચ પસંદગીઓ ({branches}) સાથે કોઈ વિકલ્પ મેળ ખાતો નથી."
        ),
        "all_safe": (
            "તમારો રેન્ક આ ક્વોટાના બધા પ્રકાશિત કટઓફ કરતાં સારો છે, તેથી દરેક પ્રોગ્રામ "
            "તમારી પહોંચમાં છે. નીચે સૌથી સ્પર્ધાત્મક વિકલ્પો છે — તમારા રેન્ક માટે સૌથી "
            "મજબૂત કોલેજો."
        ),
        "no_safe": (
            "આ ક્વોટામાં કોઈ પ્રોગ્રામ તમારા રેન્કથી એટલો આગળ બંધ થયો નથી કે તેને સુરક્ષિત "
            "બેકઅપ ગણી શકાય. નીચે જે છે તે Target અથવા Dream છે, તેથી બીજી પરીક્ષાઓ અને "
            "મેનેજમેન્ટ ક્વોટા ખુલ્લા રાખો."
        ),
        "curated": (
            "તમે જે {total} વિકલ્પો માટે પાત્ર છો તેમાંથી સૌથી મજબૂત {shown} બતાવી રહ્યા "
            "છીએ — શ્રેષ્ઠ પહેલા, દરેક કોલેજમાંથી વધુમાં વધુ {per} પ્રોગ્રામ."
        ),
    },
    "kn": {
        "pure_science": (
            "COMEDK ಕೇವಲ B.E./B.Tech ಕಾರ್ಯಕ್ರಮಗಳಿಗೆ ಪ್ರವೇಶ ನೀಡುತ್ತದೆ — ಈ ಪರೀಕ್ಷೆ "
            "ಮೂಲಕ B.Sc. ಮಾರ್ಗವಿಲ್ಲ. ಕೆಳಗಿನ ಫಲಿತಾಂಶಗಳನ್ನು ವಿಜ್ಞಾನ-ಸಂಬಂಧಿತ "
            "ಇಂಜಿನಿಯರಿಂಗ್ ಬ್ರಾಂಚ್‌ಗಳ (Biotechnology, Biomedical, Chemical) ಕಡೆಗೆ ಜೋಡಿಸಲಾಗಿದೆ."
        ),
        "kkr_not_easier": (
            "ಗಮನಿಸಿ: KKR ಸೀಟು ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಸುಲಭವಲ್ಲ. ಹೆಚ್ಚಿನ ಕಾರ್ಯಕ್ರಮಗಳಲ್ಲಿ "
            "KKR ಪೂಲ್ GM ಗಿಂತ ಮೊದಲು ಮುಚ್ಚಲ್ಪಡುತ್ತದೆ. ಪ್ರತಿ ಕಾರ್ಡ್‌ನಲ್ಲಿ KKR gap ಪರಿಶೀಲಿಸಿ."
        ),
        "branch_filter": (
            "ನಿಮ್ಮ ಆದ್ಯತೆಯ ಬ್ರಾಂಚ್‌ಗಳನ್ನು ಮಾತ್ರ ತೋರಿಸಲಾಗುತ್ತಿದೆ ({branches}). "
            "ಎಲ್ಲಾ ಆಯ್ಕೆಗಳನ್ನು ನೋಡಲು ಫಿಲ್ಟರ್ ತೆರವುಗೊಳಿಸಿ."
        ),
        "branch_filter_empty": (
            "ನಿಮ್ಮ ಬ್ರಾಂಚ್ ಆದ್ಯತೆಗಳಿಗೆ ({branches}) ಯಾವುದೇ ಆಯ್ಕೆಗಳು ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ."
        ),
        "all_safe": (
            "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಈ ಕೋಟಾದ ಎಲ್ಲಾ ಪ್ರಕಟಿತ ಕಟ್‌ಆಫ್‌ಗಳಿಗಿಂತ ಉತ್ತಮವಾಗಿದೆ, ಆದ್ದರಿಂದ ಪ್ರತಿ "
            "ಕಾರ್ಯಕ್ರಮವೂ ನಿಮ್ಮ ವ್ಯಾಪ್ತಿಯಲ್ಲಿದೆ. ಕೆಳಗೆ ಅತ್ಯಂತ ಸ್ಪರ್ಧಾತ್ಮಕ ಆಯ್ಕೆಗಳಿವೆ — ನಿಮ್ಮ "
            "ರ‍್ಯಾಂಕ್‌ಗೆ ಸಿಗುವ ಅತ್ಯುತ್ತಮ ಕಾಲೇಜುಗಳು."
        ),
        "no_safe": (
            "ಈ ಕೋಟಾದಲ್ಲಿ ಯಾವುದೇ ಕಾರ್ಯಕ್ರಮ ನಿಮ್ಮ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಸುರಕ್ಷಿತ ಬ್ಯಾಕಪ್ ಎನ್ನುವಷ್ಟು ಮುಂದೆ "
            "ಮುಚ್ಚಲ್ಪಟ್ಟಿಲ್ಲ. ಕೆಳಗಿನವು Target ಅಥವಾ Dream ಆಗಿವೆ, ಆದ್ದರಿಂದ ಇತರ ಪರೀಕ್ಷೆಗಳು ಮತ್ತು "
            "ಮ್ಯಾನೇಜ್‌ಮೆಂಟ್ ಕೋಟಾ ಆಯ್ಕೆಗಳನ್ನು ತೆರೆದಿಡಿ."
        ),
        "curated": (
            "ನೀವು ಅರ್ಹರಾಗಿರುವ {total} ಆಯ್ಕೆಗಳಲ್ಲಿ ಅತ್ಯುತ್ತಮ {shown} ಅನ್ನು ತೋರಿಸಲಾಗುತ್ತಿದೆ — "
            "ಉತ್ತಮವಾದವು ಮೊದಲು, ಪ್ರತಿ ಕಾಲೇಜಿನಿಂದ ಗರಿಷ್ಠ {per} ಕಾರ್ಯಕ್ರಮಗಳು."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Core engine functions
# ═══════════════════════════════════════════════════════════════════════════

# COMEDK's cutoff model. Shared with KCET — same formulas, COMEDK's own
# constants, measured from this dataset's distribution (see config.py).
#
# dynamic_floor_fraction lowers the target-band floor for very competitive
# programmes: at cutoff 692 a flat 1,000-rank floor would swallow the whole
# rank range below it and stop top ranks reading as Safe. KCET does not need
# this and leaves it None.
CUTOFF_MODEL = PointCutoffModel(
    safe_margin=SAFE_MARGIN,
    target_band_floor=TARGET_BAND_FLOOR,
    target_band_ceiling=TARGET_BAND_CEILING,
    upper_margin=UPPER_MARGIN,
    reach_band_ceiling=REACH_BAND_CEILING,
    sigma_fraction=SIGMA_FRACTION,
    sigma_floor=SIGMA_FLOOR,
    sigma_ceiling=SIGMA_CEILING,
    steepness=STEEPNESS,
    dynamic_floor_fraction=0.5,
)

_target_band = CUTOFF_MODEL.target_band
_reach_band = CUTOFF_MODEL.reach_band
_categorize = CUTOFF_MODEL.categorize
_calculate_probability = CUTOFF_MODEL.probability


def _confidence(rank: int, cutoff: float) -> str:
    """Headroom-based confidence — no fabricated volatility.

    COMEDK has one round, so there is no spread to measure. What *can* be
    stated factually is how far the student sits from the decision boundary.
    Uses the *same* z-score that drives the probability, so the label and the
    percentage on a card can never disagree.

        |z| < 0.5   ->  borderline   (roughly 46-54 % — a coin flip)
        z  >= 1.5   ->  high         (roughly 90 % and up)
        otherwise   ->  medium

    Three values, deliberately not shared: KCET uses two (no ``borderline``)
    and JEE uses four round-volatility tags. Same field name, different
    questions.
    """
    z = CUTOFF_MODEL.z_score(rank, cutoff)
    if abs(z) < 0.5:
        return "borderline"
    if z >= 1.5:
        return "high"
    return "medium"



def _quality_score(competitiveness: float, brand_score: float) -> float:
    """Option quality on a 0–10 scale, used to order results inside a bucket.

    Blends the programme's own cutoff percentile within its quota (the sharpest
    demand signal a single-cutoff dataset offers) with the institute's brand
    tier (only five distinct values, so it acts as a tiebreaker rather than the
    primary key).  Ordering by brand alone put a good college's Automobile
    branch above a strong college's CSE at rank 60,000.
    """
    return 10.0 * (W_COMPETITIVENESS * competitiveness + W_BRAND * brand_score)


def _group_and_order(nodes: List[ComedkProgramNode]) -> Dict[str, List[ComedkProgramNode]]:
    """Bucket the scored rows, each bucket best-first — see ``core.curation``.

    COMEDK's cutoff attribute is ``cutoff_rank`` and its programme name is
    ``branch``; KCET names the same two things ``closing_rank`` and ``program``.
    Naming them at the call site is what lets one implementation serve both
    without either schema knowing about the other.
    """
    return curation.group_and_order(
        nodes, rank_attr="cutoff_rank", name_attr="branch"
    )


# Signature is identical to the shared implementation, so this is a plain
# alias rather than a wrapper.
_curate_bucket = curation.curate_bucket


def _brand_phrase(brand_tier: str, lang: str = "en") -> str:
    """Short, factual brand-tier phrase for the reason sentence."""
    p = _BRAND_PHRASES.get(lang, _BRAND_PHRASES["en"])
    return p.get(brand_tier, p["emerging"])


def _build_reason(
    branch: str,
    brand_tier: str,
    category: str,
    matched: bool,
    conf: str,
    kkr_gap: Optional[float],
    quota: str,
    lang: str = "en",
) -> str:
    """Compose a one-to-two sentence factual explanation."""
    t = _REASON_TEXT.get(lang, _REASON_TEXT["en"])
    clauses: List[str] = []

    lead = t["lead"].format(category=category)
    fit = t["matched"] if matched else t["unmatched"]
    clauses.append(
        t["clause0"].format(
            lead=lead, fit=fit, branch=branch, brand=_brand_phrase(brand_tier, lang),
        )
    )

    # KKR gap — report the sign honestly
    if kkr_gap is not None and quota == "KKR":
        if kkr_gap > 0:
            clauses.append(t["kkr_positive"].format(n=int(abs(kkr_gap))))
        elif kkr_gap < 0:
            clauses.append(t["kkr_negative"].format(n=int(abs(kkr_gap))))

    sentence = clauses[0]
    if len(clauses) > 1:
        sentence += t["and"] + t["and"].join(clauses[1:])

    tail = _CONFIDENCE_TAIL.get(lang, _CONFIDENCE_TAIL["en"])[conf]
    return f"{sentence}. {tail}"


# ═══════════════════════════════════════════════════════════════════════════
# Main recommendation entry point
# ═══════════════════════════════════════════════════════════════════════════

def recommend(req: ComedkRecommendRequest) -> ComedkRecommendResponse:
    """Generate recommendations for a COMEDK student.

    Pipeline mirrors JEE: filter → categorise → score → explain → order → curate.

    The curate stage is what makes this a recommender rather than a table
    viewer.  Every eligible programme is scored and counted; the default
    response then shows the best few per bucket.  Requesting a single bucket
    (``bucket="safe"`` and friends) opts out of the caps and returns that
    bucket's complete ordered list, paginated — so nothing is ever unreachable.
    """
    programs = get_programs()
    lang = req.lang if req.lang in ("en", "hi", "gu", "kn") else "en"
    notes_text = _NOTES.get(lang, _NOTES["en"])
    notes: List[str] = []

    # ── Sanity bound on the rank itself ──────────────────────────────────
    # settings.max_rank exists to catch a mistyped rank (a student entering their
    # marks, or an extra digit).  Without this the request still "works" — it
    # just returns an empty list, which reads as "no colleges for you" rather
    # than "check what you typed".
    if req.rank > settings.max_rank:
        return ComedkRecommendResponse(
            guidance=_GUIDANCE.get(lang, _GUIDANCE["en"])["rank_implausible"].format(
                rank=req.rank, max_rank=settings.max_rank,
            ),
            notes=[
                _GUIDANCE.get(lang, _GUIDANCE["en"])["rank_implausible"].format(
                    rank=req.rank, max_rank=settings.max_rank,
                )
            ],
            counts={
                "total": 0,
                "shown": 0,
                "total_attainable": 0,
                "curated": False,
                "by_category": {
                    "Safe": 0, "Target": 0, "Reach": 0,
                    "Safe_total_attainable": 0,
                    "Target_total_attainable": 0,
                    "Reach_total_attainable": 0,
                },
            },
        )

    # ── Optional explicit branch-family filter ───────────────────────────
    wanted_families: Set[str] = set()
    if req.branch_families:
        wanted_families = {
            f for f in req.branch_families if f in states.VALID_BRANCH_PREFERENCES
        }

    # ── Pure science note removed — goal is no longer part of the flow ──

    # ── KKR note ─────────────────────────────────────────────────────────
    if req.quota == "KKR":
        notes.append(notes_text["kkr_not_easier"])

    # ── Cutoff extremes in this quota, for edge-case messaging ───────────
    quota_programs = [p for p in programs if p["quota"] == req.quota]
    max_cutoff = max((p["cutoff_rank"] for p in quota_programs), default=0)
    min_cutoff = min((p["cutoff_rank"] for p in quota_programs), default=0)

    # ── Filter → categorise → score → explain ────────────────────────────
    all_matches: List[ComedkProgramNode] = []

    for prog in programs:
        # Quota filter — hard filter
        if prog["quota"] != req.quota:
            continue

        # Branch-family filter — hard filter, only when explicitly requested
        if wanted_families and prog["branch_family"] not in wanted_families:
            continue

        cutoff = prog["cutoff_rank"]
        bucket = _categorize(req.rank, cutoff)
        if bucket is None:
            continue

        score = _quality_score(prog.get("competitiveness", 0.0), prog["brand_score"])
        prob = _calculate_probability(req.rank, cutoff)
        conf = _confidence(req.rank, cutoff)
        rank_gap = int(cutoff - req.rank)  # positive = student ahead of cutoff

        reason = _build_reason(
            branch=prog["branch"],
            brand_tier=prog["brand_tier"],
            category=bucket,
            matched=False,
            conf=conf,
            kkr_gap=prog.get("kkr_gap"),
            quota=prog["quota"],
            lang=lang,
        )

        node = ComedkProgramNode(
            # Legacy fields
            institute=prog["institute"],
            program=prog["program"],
            quota=prog["quota"],
            cutoff_rank=cutoff,
            bucket=bucket,
            tags=[prog["branch_family"]],
            # New fields
            category=bucket,
            fit_label=FIT_LABELS.get(lang, FIT_LABELS["en"])[bucket],
            reason=reason,
            admission_probability=prob,
            confidence=conf,
            interest_score=round(score, 2),
            matched_interest=False,
            rank_gap=rank_gap,
            brand_score=prog["brand_score"],
            brand_tier=prog["brand_tier"],
            is_metro=prog["is_metro"],
            kkr_gap=prog.get("kkr_gap"),
            branch=prog["branch"],
            branch_family=prog["branch_family"],
            degree=prog["degree"],
        )
        all_matches.append(node)

    # ── Order each bucket best-first ─────────────────────────────────────
    eligible = _group_and_order(all_matches)

    # Everything the student is eligible for.
    count_target = len(eligible["Target"])
    count_reach = len(eligible["Reach"])
    count_safe = len(eligible["Safe"])
    total_all = count_target + count_reach + count_safe

    # ── Top-rank fallback ────────────────────────────────────────────────
    # For exceptional ranks (≤ TOP_RANK_THRESHOLD), every programme is Safe
    # and the three-bucket framing provides no signal.  Show a curated
    # shortlist of the TOP_RANK_CAP most competitive programmes with
    # institute diversity — mirroring JEE's _apply_top_rank_fallback().
    # COMEDK is the only exam passing a rank_gate: JEE and KCET derive
    # top-rank purely from the bucket counts.
    is_top_rank = curation.detect_top_rank(
        total_all,
        count_target,
        count_reach,
        rank=req.rank,
        rank_gate=TOP_RANK_THRESHOLD,
    )

    # Precedence is COMEDK's own: top-rank mode wins over a single-bucket
    # request.  The shortlist is built first and the bucket filter then runs
    # over it, so `rank 50, bucket=safe` answers with the 10 most competitive
    # programmes rather than a paginated walk through all 832 the rank clears.
    # KCET resolves the same collision the other way round; see the note in its
    # recommender.
    if is_top_rank:
        # Curate: pick the top N most competitive with institute diversity
        curated = curation.top_rank_view(eligible, TOP_RANK_CAP, MAX_PER_INSTITUTE)
    else:
        # A single-bucket request opts out of the caps entirely: the bucket
        # filter and pagination below return that bucket's complete ordered
        # list, so nothing eligible is ever unreachable.
        single_bucket = req.bucket in ("safe", "target", "reach", "dream")
        if single_bucket:
            curated = dict(eligible)
        else:
            curated = curation.curate_all(eligible, BUCKET_CAPS, MAX_PER_INSTITUTE)

    count_target_shown = len(curated["Target"])
    count_reach_shown = len(curated["Reach"])
    count_safe_shown = len(curated["Safe"])

    # Flat list in the shared display order: Target, then Reach, then Safe.
    selected = curation.flatten(curated)

    total_unfiltered = len(selected)
    single_bucket = req.bucket in ("safe", "target", "reach", "dream")
    is_curated = is_top_rank or (not single_bucket and total_unfiltered < total_all)

    total_by_type = {
        "safe": {"total": count_safe_shown, "total_attainable": count_safe},
        "target": {"total": count_target_shown, "total_attainable": count_target},
        "dream": {"total": count_reach_shown, "total_attainable": count_reach},
        "all": {"total": total_unfiltered, "total_attainable": total_all},
    }

    counts = {
        "total": total_unfiltered,
        "shown": total_unfiltered,  # updated after pagination
        "total_attainable": total_all,
        "curated": is_curated,
        "by_category": {
            "Safe": count_safe_shown,
            "Target": count_target_shown,
            "Reach": count_reach_shown,
            "Safe_total_attainable": count_safe,
            "Target_total_attainable": count_target,
            "Reach_total_attainable": count_reach,
        },
    }

    # ── Branch filter notes ──────────────────────────────────────────────
    if wanted_families:
        branch_names = ", ".join(
            states.BRANCH_LABELS.get(f, f) for f in sorted(wanted_families)
        )
        note_key = "branch_filter" if total_all else "branch_filter_empty"
        notes.append(notes_text[note_key].format(branches=branch_names))

    # ── Edge case: rank better than every published cutoff ───────────────
    if total_all > 0 and min_cutoff > 0 and req.rank <= min_cutoff:
        notes.append(notes_text["all_safe"])

    # ── Edge case: no safe backup exists at this rank ─────────────────────
    if total_all > 0 and count_safe == 0:
        notes.append(notes_text["no_safe"])

    # ── Edge case: rank past highest cutoff ──────────────────────────────
    rank_beyond_data = req.rank > max_cutoff if max_cutoff > 0 else False
    if rank_beyond_data:
        if total_all > 0:
            notes.append(
                _GUIDANCE.get(lang, _GUIDANCE["en"])["beyond_data"].format(
                    rank=req.rank, max_cutoff=int(max_cutoff),
                )
            )
        else:
            notes.append(
                _GUIDANCE.get(lang, _GUIDANCE["en"])["no_results_beyond"].format(
                    rank=req.rank, max_cutoff=int(max_cutoff),
                )
            )

    # ── Curation footnote ────────────────────────────────────────────────
    if is_curated:
        notes.append(
            notes_text["curated"].format(
                shown=total_unfiltered,
                total=total_all,
                per=MAX_PER_INSTITUTE,
            )
        )

    # ── Bucket filter ────────────────────────────────────────────────────
    if req.bucket == "safe":
        filtered = [r for r in selected if r.category == "Safe"]
    elif req.bucket == "target":
        filtered = [r for r in selected if r.category == "Target"]
    elif req.bucket in ("reach", "dream"):
        filtered = [r for r in selected if r.category == "Reach"]
    else:
        filtered = selected

    # ── Pagination (applies to whatever bucket was selected) ─────────────
    start_idx = (req.page - 1) * req.page_size
    end_idx = start_idx + req.page_size
    page_results = filtered[start_idx:end_idx]
    has_next = end_idx < len(filtered)

    counts["shown"] = len(page_results)

    # ── Legacy bucket lists ──────────────────────────────────────────────
    page_safe = [r for r in page_results if r.category == "Safe"]
    page_target = [r for r in page_results if r.category == "Target"]
    page_reach = [r for r in page_results if r.category == "Reach"]

    # ── Guidance text ────────────────────────────────────────────────────
    guidance_text = _GUIDANCE.get(lang, _GUIDANCE["en"])
    if total_all == 0 and not rank_beyond_data:
        overall = guidance_text["empty"]
    elif total_all == 0 and rank_beyond_data:
        overall = ""  # the note already covers this
    else:
        # "total" is everything the student is eligible for, not the shortlist —
        # the shortlist size is what "shown" reports.
        overall = guidance_text["found"].format(
            total=total_all, shown=len(page_results),
        )

    # ── Category guidance blurbs ─────────────────────────────────────────
    blurbs = CATEGORY_BLURBS.get(lang, CATEGORY_BLURBS["en"])
    category_guidance = [
        ComedkCategoryGuidance(
            category=c,
            count=counts["by_category"][c],
            blurb=blurbs[c],
        )
        for c in CATEGORY_ORDER
        if counts["by_category"][c] > 0
    ]

    # ── Interest guidance removed — goal is no longer part of the flow ───
    interest_guidance = ""

    return ComedkRecommendResponse(
        # Legacy fields
        safe=page_safe,
        target=page_target,
        reach=page_reach,
        total_safe=count_safe_shown,
        total_target=count_target_shown,
        total_reach=count_reach_shown,
        has_next=has_next,
        # New JEE-parallel fields
        guidance=overall,
        interest_guidance=interest_guidance,
        counts=counts,
        notes=notes,
        category_guidance=category_guidance,
        recommendations=page_results,
        total_count=total_unfiltered,
        total_by_type=total_by_type,
        thresholds={
            "safe_margin": SAFE_MARGIN,
            "upper_margin": UPPER_MARGIN,
            "target_band_floor": TARGET_BAND_FLOOR,
            "target_band_ceiling": TARGET_BAND_CEILING,
            "reach_band_ceiling": REACH_BAND_CEILING,
            "caps": dict(BUCKET_CAPS),
            "top_rank_threshold": TOP_RANK_THRESHOLD,
            "top_rank_cap": TOP_RANK_CAP,
            "max_per_institute": MAX_PER_INSTITUTE,
        },
    )
