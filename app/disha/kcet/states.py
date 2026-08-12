"""Static lookups for the KCET engine: quota/category parsing, branch
classification, and career-goal weighting.

Deliberately self-contained — no imports from ``app.disha.states`` (the JEE
module) or from ``app.disha.comedk``. KCET's category codes, course-name
vocabulary and quota semantics are different enough from JoSAA's that sharing
a module would couple two engines that should be able to change independently.

Why classification is keyword-bag based, not phrase based
-----------------------------------------------------------
JEE's ``classify_branch()`` matches phrases like "computer science and
engineering" because JoSAA's names are clean. KCET's ``course_name`` column in
this dataset is not: it looks like a table scrape that reordered or truncated
words, e.g. "COMMUNICATION ENGG INFORMATION" (Information Science and
Engineering) or "ARTIFICIAL" alone (Artificial Intelligence and Machine
Learning, truncated). Word order cannot be trusted, so ``classify_kcet_branch``
searches for keyword fragments anywhere in the string rather than phrases.
The raw ``course_name`` is still shown on cards unmodified — tags drive
filtering and scoring, not display, so a keyword miss never invents a wrong
program name.
"""

from __future__ import annotations

from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Quota/category parsing.
#
# The `category` column encodes two independent things in one code: a
# reservation category and a home-region eligibility suffix.
#   Reservation:  GM (General Merit), 1G/1K/1R, 2AG/2AK/2AR, 2BG/2BK/2BR,
#                 3AG/3AK/3AR, 3BG/3BK/3BR, SCG/SCK/SCR, STG/STK/STR
#   Region suffix: G = state-wide (General), K = Kalyana Karnataka
#                 (Hyderabad-Karnataka, Article 371J) home-region quota,
#                 R = Rural home-region quota.
# This module only *labels* that split for display (cards, stats); it does not
# attempt to infer a student's regional eligibility. The recommend request
# still takes the exact published code (e.g. "2AG"), matching how a student
# reads their own KEA rank card — same reasoning as JEE's exact seat_type
# match, and it avoids guessing eligibility rules this repo has no data to
# verify.
# ---------------------------------------------------------------------------
_REGION_SUFFIX_LABEL = {
    "G": "State-wide (General)",
    "K": "Kalyana Karnataka (Hyderabad-Karnataka) home-region quota",
    "R": "Rural home-region quota",
}

_BASE_CATEGORY_LABEL = {
    "GM": "General Merit",
    "1": "Category 1",
    "2A": "Category 2A",
    "2B": "Category 2B",
    "3A": "Category 3A",
    "3B": "Category 3B",
    "SC": "Scheduled Caste",
    "ST": "Scheduled Tribe",
}


def parse_category(code: str) -> tuple[str, str]:
    """Split a KCET category code into (base_category, region_suffix).

    "2AG" -> ("2A", "G"); "SCK" -> ("SC", "K"); "GM" has no region suffix
    (state-wide by definition) -> ("GM", "G"). Unknown codes fall back to
    (code, "G") so display code never crashes on an unexpected value.
    """
    code = (code or "").strip().upper()
    if code == "GM":
        return "GM", "G"
    if len(code) >= 2 and code[-1] in "GKR" and code[:-1] in _BASE_CATEGORY_LABEL:
        return code[:-1], code[-1]
    return code, "G"


def describe_category(code: str) -> str:
    """Human-readable label for a category code, e.g. "2AG" -> "Category 2A
    (State-wide)"."""
    base, region = parse_category(code)
    base_label = _BASE_CATEGORY_LABEL.get(base, base)
    region_label = _REGION_SUFFIX_LABEL.get(region, "State-wide")
    if base == "GM":
        return base_label
    return f"{base_label} ({region_label})"


# ---------------------------------------------------------------------------
# Branch classification: map a (messy) course name to a set of semantic tags.
# ---------------------------------------------------------------------------
def classify_kcet_branch(course_name: str) -> Set[str]:
    p = (course_name or "").upper()
    # A handful of names carry a stray mid-word space from the source scrape
    # ("BLO CK CHAIN", "CYB ER SECURITY", "DAT A SCIENCE", "AI &ML") that
    # breaks a plain substring search. A whitespace-collapsed copy catches
    # those without weakening the primary (spaced) keyword checks below.
    p_compact = p.replace(" ", "").replace("&", "")
    tags: Set[str] = set()

    def has(*keys: str) -> bool:
        return any(k in p for k in keys)

    def has_compact(*keys: str) -> bool:
        return any(k in p_compact for k in keys)

    # Computing-oriented
    if has("ARTIFICIAL", "INTELLIGENCE", "MACHINE LEARNING"):
        tags.add("ai_ds")
    if has("DATA SCIENCE", "DATA SCIENCES", "DATA ANALYTICS", "BIG DATA"):
        tags.add("ai_ds")
    if has("CYBER SECURITY", "BLOCK CHAIN", "CLOUD COMPUTING", "DEV OPS", "DEVOPS",
           "FULL STACK", "SOFTWARE PRODUCT", "COMPUTER SCIENCE", "COMPUTER ENGINEERING",
           "COMPUTER", "BUSINESS SYSTEMS", "VIRTUAL REALITY", "VIRUTAL REALITY", "AR/VR"):
        tags.add("cse")
    if has("INFORMATION SCIENCE", "INFORMATION TECHNOLOGY", "INFORMATION 5",
           "INFORMATION" ) and "ARTIFICIAL" not in p:
        tags.add("it")
    if has("MATHAMATICS AND COMPUTING", "MATHEMATICS AND COMPUTING"):
        tags.add("math_computing")
    if has("VLSI", "EMBEDDED SYSTEM", "IOT", "INTERNET OF THINGS"):
        tags.add("cse")
    if has_compact("BLOCKCHAIN", "CYBERSECURITY", "DATASCIENCE", "SOFTWAREPRODUCT", "AIML"):
        tags.add("cse")

    # Electronics / electrical / instrumentation
    if has("ELECTRONICS", "COMMUNICATION", "TELECOMMUNICAT"):
        tags.add("ece")
    if has("ELECTRICAL"):
        tags.add("electrical")
    if has("INSTRUMENTATION"):
        tags.add("ece")

    # Core mechanical / civil / chemical / aero / materials / production
    if has("MECHANICAL", "MECHATRONICS"):
        tags.add("mechanical")
    if has("CIVIL", "CONSTRUCTION"):
        tags.add("civil")
    if has("CHEMICAL"):
        tags.add("chemical")
    if has("AERO", "AERONAUTICAL", "AVIATION", "SPACE ENGINEERING"):
        tags.add("aerospace")
    if has("CERAMICS", "POLYMER", "METALLURG"):
        tags.add("materials")
    if has("INDUSTRIAL", "PRODUCTION", "AUTOMATION", "AUTOMOTIVE", "ROBOTIC",
           "MANUFACTURING"):
        tags.add("production")
    if has("BIO-TECHNOLOGY", "BIOTECHNOLOGY", "BIO- TECHNOLOGY", "BIO-MEDICAL",
           "BIOMEDICAL", "BIO-"):
        tags.add("biotech")

    # Branches unique to this dataset's vocabulary (no JEE/COMEDK equivalent
    # tag existed, so these are new — kept separate rather than mis-tagged
    # into "mechanical"/"chemical" so goal-weighting stays honest).
    if has("AGRICULTUR"):
        tags.add("agriculture")
    if has("MINING"):
        tags.add("mining")
    if has("PETROLEUM"):
        tags.add("petroleum")
    if has("MARINE"):
        tags.add("marine")
    if has("TEXTILE", "SILK TECHNOLOGY"):
        tags.add("textile")
    if has("FASHION DESIGN", "LIFE STYLE", "DESIGN") and "MECHANICAL" not in p:
        tags.add("design")

    if not tags:
        tags.add("other")
    return tags


# ---------------------------------------------------------------------------
# Career goals -> tag weights. Six goals for product consistency with the JEE
# and COMEDK engines, but weights and tag vocabulary are KCET-specific: this
# dataset has agriculture/mining/petroleum/marine/textile branches that
# JEE/COMEDK's engineering set does not.
# ---------------------------------------------------------------------------
GOAL_TAG_WEIGHTS: Dict[str, Dict[str, float]] = {
    "coding": {
        "cse": 10,
        "ai_ds": 9,
        "math_computing": 9,
        "it": 8,
        "ece": 6,
        "electrical": 4,
    },
    "research": {
        "ai_ds": 7,
        "math_computing": 7,
        "biotech": 7,
        "cse": 5,
        "ece": 5,
        "materials": 5,
        "mechanical": 4,
        "chemical": 4,
    },
    "pure_science": {
        # KCET's seats are all engineering programmes — nothing here is a pure
        # BS Physics/Chemistry/Maths degree the way JEE's Engineering Physics
        # or BS programmes are. Biotech and materials are the closest
        # science-adjacent branches on offer, so they carry the weight
        # instead of leaving this goal with an empty, uninformative mapping.
        "biotech": 8,
        "materials": 6,
        "chemical": 5,
    },
    "mba": {
        "cse": 6,
        "math_computing": 6,
        "ece": 5,
        "mechanical": 5,
        "electrical": 5,
        "civil": 4,
        "chemical": 4,
    },
    "core": {
        "mechanical": 10,
        "civil": 9,
        "electrical": 9,
        "chemical": 9,
        "aerospace": 9,
        "materials": 8,
        "production": 8,
        "mining": 7,
        "petroleum": 7,
        "marine": 7,
        "textile": 6,
        "agriculture": 6,
        "ece": 6,
        "cse": 3,
    },
    "undecided": {
        "cse": 7,
        "ece": 7,
        "ai_ds": 7,
        "math_computing": 7,
        "electrical": 6,
        "mechanical": 6,
        "chemical": 5,
        "civil": 5,
        "it": 6,
    },
}

GOAL_LABELS: Dict[str, str] = {
    "coding": "Software / coding career",
    "research": "Research / higher studies",
    "pure_science": "Science-adjacent (Biotech, Materials, Chemical)",
    "mba": "Management / MBA / business",
    "core": "Core engineering",
    "undecided": "Undecided / keeping options open",
}

GOAL_GUIDANCE: Dict[str, str] = {
    "coding": (
        "Since you are aiming for a software/coding career, Computer Science, "
        "AI/Data Science, IT and VLSI/embedded programmes are ranked highest "
        "for you."
    ),
    "research": (
        "For a research or higher-studies path, AI/Data Science, Biotechnology "
        "and core-science-adjacent branches at colleges with strong labs are "
        "prioritised."
    ),
    "pure_science": (
        "KCET's seats are all engineering programmes, so the closest fit to a "
        "pure-science interest is Biotechnology, Materials and Chemical "
        "Engineering — prioritised here."
    ),
    "mba": (
        "If you are leaning towards management/MBA later, any branch works; "
        "quantitative branches like CS and Electronics add a small edge, and "
        "the college's overall competitiveness matters more than the branch."
    ),
    "core": (
        "For a core-engineering career, Mechanical, Civil, Electrical, "
        "Chemical, Aerospace, Mining, Petroleum, Marine and Textile branches "
        "are ranked highest."
    ),
    "undecided": (
        "Since you are still deciding, the list favours versatile, "
        "high-demand branches (CS, ECE, AI/DS, Electrical, Mechanical) that "
        "keep the most doors open."
    ),
}

VALID_GOALS: List[str] = list(GOAL_TAG_WEIGHTS.keys())

# ---------------------------------------------------------------------------
# Branch preferences: a friendly set of branch families a student can filter
# results by, mirroring the shape of JEE's BRANCH_PREFERENCES.
# ---------------------------------------------------------------------------
BRANCH_PREFERENCES: List[dict] = [
    {"value": "cse", "label": "Computer Science", "tags": ["cse"]},
    {"value": "it", "label": "Information Science / IT", "tags": ["it"]},
    {"value": "ai_ds", "label": "AI / Data Science", "tags": ["ai_ds"]},
    {"value": "ece", "label": "Electronics & Communication", "tags": ["ece"]},
    {"value": "electrical", "label": "Electrical", "tags": ["electrical"]},
    {"value": "mechanical", "label": "Mechanical", "tags": ["mechanical"]},
    {"value": "civil", "label": "Civil", "tags": ["civil"]},
    {"value": "chemical", "label": "Chemical", "tags": ["chemical"]},
    {"value": "aerospace", "label": "Aeronautical / Aerospace", "tags": ["aerospace"]},
    {"value": "biotech", "label": "Biotechnology", "tags": ["biotech"]},
    {"value": "production", "label": "Industrial / Production / Robotics", "tags": ["production"]},
    {"value": "other_core", "label": "Mining / Petroleum / Marine / Textile", "tags": ["mining", "petroleum", "marine", "textile"]},
]

BRANCH_PREFERENCE_TAGS: Dict[str, Set[str]] = {
    b["value"]: set(b["tags"]) for b in BRANCH_PREFERENCES
}
VALID_BRANCH_PREFERENCES = list(BRANCH_PREFERENCE_TAGS.keys())


def tags_for_branch_preferences(prefs: List[str]) -> Set[str]:
    wanted: Set[str] = set()
    for p in prefs or []:
        wanted |= BRANCH_PREFERENCE_TAGS.get(p, set())
    return wanted
