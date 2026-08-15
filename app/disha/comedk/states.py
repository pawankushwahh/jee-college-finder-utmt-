"""Branch classification, goal weights and branch-preference metadata for COMEDK.

Mirrors ``app/disha/states.py`` in public surface:

    classify_branch(program)   – returns a *single* family string
    GOAL_TAG_WEIGHTS           – dict[goal][family] -> int (0..10)
    VALID_GOALS                – list of valid goal strings
    BRANCH_PREFERENCES         – list of {value, label}
    VALID_BRANCH_PREFERENCES   – list of valid preference value strings
    BRANCH_LABELS              – dict mapping family -> human-readable label

**Key difference from JEE:**
JEE's ``classify_branch`` returns a *set* of tags because JEE programme names
are generic enough that a single programme may span multiple families (e.g.
"Electronics and Communication Engineering" gets both ``ece`` and ``electrical``).
COMEDK programme names, by contrast, are specific enough to place each row in
exactly *one* family — so this function returns a ``str``, not a ``Set[str]``.

**Geography note:**
All COMEDK colleges are in Karnataka. JEE's home-state vs other-state machinery
(``INDIAN_STATES``, ``INSTITUTE_STATE``, ``SPECIAL_QUOTA_STATE``,
``get_institute_state``) has no equivalent here, and that absence is intentional.
"""

from __future__ import annotations

import re
from typing import Dict, List


# ---------------------------------------------------------------------------
# Branch-family classifier.
#
# Ordered *most-specific first* so that
#   "Computer Science & Engineering (Data Science)"  →  ai_ds
#   "Computer Science & Engineering (Cyber Security)" →  cyber
# rather than the broader "cse".
#
# The regex list is tested top-to-bottom; first match wins.
# ---------------------------------------------------------------------------

_BRANCH_RULES: List[tuple[re.Pattern, str]] = [
    # ── Robotics & Artificial Intelligence (must precede generic AI rule) ─
    (re.compile(r"robotics\s*&\s*artificial intelligence", re.I), "robotics"),

    # ── AI / Data Science specialisations ────────────────────────────────
    (re.compile(r"artificial intelligence.*machine learning|ai.*ml", re.I), "ai_ds"),
    (re.compile(r"artificial intelligence.*data science|data science|data analytics|big data", re.I), "ai_ds"),
    (re.compile(r"artificial intelligence|machine learning", re.I), "ai_ds"),

    # ── Cyber Security ───────────────────────────────────────────────────
    (re.compile(r"cyber security|block\s*chain|iot.*cyber|iot.*block", re.I), "cyber"),

    # ── VLSI ─────────────────────────────────────────────────────────────
    (re.compile(r"vlsi", re.I), "vlsi"),

    # ── Robotics / Automation ────────────────────────────────────────────
    (re.compile(r"robotics|automation\s*&\s*robotics|robotics\s*&\s*automation", re.I), "robotics"),

    # ── Design ───────────────────────────────────────────────────────────
    (re.compile(r"bachelor of design|communication\s*&\s*design|computer science\s*&\s*design", re.I), "design"),

    # ── EEE / Electrical (must precede ECE and CSE to catch "Electrical & Electronics",
    #    "Electrical & Computer" before the broader electronics/computer rules) ────
    (re.compile(r"electrical\s*&\s*electronics|electrical\s*&\s*computer", re.I), "eee"),

    # ── ECE / Telecom / Instrumentation (must precede CSE to catch
    #    "Electronics & Computer" before the generic "computer" rule) ──────
    (re.compile(r"electronics\s*&\s*communicat|electronics\s*&\s*telecommunicat|electronics\s*&\s*computer|electronics\s*&\s*instrumentat|medical electronics|electronics engineering", re.I), "ece"),

    # ── CSE broad (must come AFTER the specialisations above) ────────────
    (re.compile(r"computer science|computer engineering|computer\s*&\s*communi", re.I), "cse"),

    # ── IT / Information Science ─────────────────────────────────────────
    (re.compile(r"information (science|technology)", re.I), "it"),

    # ── Biotech ──────────────────────────────────────────────────────────
    (re.compile(r"bio-?\s*tech", re.I), "biotech"),

    # ── Biomedical ───────────────────────────────────────────────────────
    (re.compile(r"bio-?\s*medical", re.I), "biomedical"),

    # ── Mechanical ───────────────────────────────────────────────────────
    (re.compile(r"mechanical", re.I), "mechanical"),

    # ── Automobile ───────────────────────────────────────────────────────
    (re.compile(r"automobile", re.I), "automobile"),

    # ── Civil ────────────────────────────────────────────────────────────
    (re.compile(r"civil", re.I), "civil"),

    # ── Chemical ─────────────────────────────────────────────────────────
    (re.compile(r"chemical", re.I), "chemical"),

    # ── Aerospace / Aeronautical ─────────────────────────────────────────
    (re.compile(r"aerospace|aeronaut", re.I), "aerospace"),

    # ── Industrial Engineering ───────────────────────────────────────────
    (re.compile(r"industrial", re.I), "industrial"),

    # ── Agriculture ──────────────────────────────────────────────────────
    (re.compile(r"agricultur", re.I), "agriculture"),
]


def classify_branch(program: str) -> str:
    """Classify a COMEDK programme name into exactly one branch family.

    Unlike JEE's ``classify_branch`` (which returns a ``set`` of tags),
    this returns a single ``str`` because COMEDK programme names are specific
    enough that each row maps unambiguously to one family.

    Returns ``"other"`` only if no rule matches — but the rules are written to
    cover all 46 programmes in the 2025 dataset, so ``"other"`` should never
    appear in practice.
    """
    for pattern, family in _BRANCH_RULES:
        if pattern.search(program):
            return family
    return "other"


# ---------------------------------------------------------------------------
# Goal → family → weight (0‥10)
# ---------------------------------------------------------------------------
GOAL_TAG_WEIGHTS: Dict[str, Dict[str, int]] = {
    "coding": {
        "cse": 10,
        "ai_ds": 9,
        "cyber": 8,
        "it": 8,
        "design": 6,       # CS & Design is still code-heavy
        "ece": 5,
        "vlsi": 4,
        "eee": 3,
        "robotics": 5,
    },
    "research": {
        "biotech": 10,
        "biomedical": 9,
        "chemical": 8,
        "aerospace": 7,
        "cse": 5,
        "ai_ds": 6,
        "ece": 5,
        "mechanical": 5,
        "civil": 4,
        "eee": 4,
        "agriculture": 6,
    },
    "pure_science": {
        # COMEDK admits to B.E./B.Tech only — no true B.Sc. pathway.
        # Rank towards the closest science-adjacent branches.
        "biotech": 8,
        "biomedical": 7,
        "chemical": 7,
        "agriculture": 5,
        "aerospace": 4,
        "cse": 3,
        "ai_ds": 3,
    },
    "mba": {
        # Institute brand dominates; any branch is fine.
        "cse": 6,
        "ai_ds": 6,
        "it": 5,
        "ece": 5,
        "mechanical": 5,
        "eee": 5,
        "civil": 4,
        "chemical": 4,
    },
    "core": {
        "mechanical": 10,
        "civil": 9,
        "eee": 9,
        "chemical": 9,
        "aerospace": 9,
        "automobile": 8,
        "industrial": 8,
        "ece": 6,
        "robotics": 6,
        "agriculture": 5,
        "cse": 3,
    },
    "undecided": {
        "cse": 7,
        "ai_ds": 7,
        "it": 6,
        "ece": 7,
        "eee": 6,
        "mechanical": 6,
        "civil": 5,
        "chemical": 5,
        "cyber": 6,
        "robotics": 5,
        "design": 5,
    },
}

VALID_GOALS: List[str] = list(GOAL_TAG_WEIGHTS.keys())


# ---------------------------------------------------------------------------
# Goal labels (reused from JEE's states module for the /meta endpoint)
# ---------------------------------------------------------------------------
GOAL_LABELS: Dict[str, str] = {
    "coding": "Software / coding career",
    "research": "Research / higher studies",
    "pure_science": "Pure Science (Physics, Chemistry, Maths)",
    "mba": "Management / MBA / business",
    "core": "Core engineering",
    "undecided": "Undecided / keeping options open",
}


# ---------------------------------------------------------------------------
# Branch preference filter options (for UI dropdown / chips)
# ---------------------------------------------------------------------------
BRANCH_PREFERENCES: List[dict] = [
    {"value": "cse",        "label": "Computer Science & Engineering"},
    {"value": "ai_ds",      "label": "AI / Data Science / ML"},
    {"value": "cyber",      "label": "Cyber Security / Blockchain / IoT"},
    {"value": "it",         "label": "Information Science / IT"},
    {"value": "ece",        "label": "Electronics & Communication"},
    {"value": "vlsi",       "label": "VLSI"},
    {"value": "eee",        "label": "Electrical & Electronics"},
    {"value": "robotics",   "label": "Robotics & Automation"},
    {"value": "mechanical", "label": "Mechanical Engineering"},
    {"value": "automobile", "label": "Automobile Engineering"},
    {"value": "civil",      "label": "Civil Engineering"},
    {"value": "chemical",   "label": "Chemical Engineering"},
    {"value": "aerospace",  "label": "Aerospace / Aeronautical"},
    {"value": "biotech",    "label": "Biotechnology"},
    {"value": "biomedical", "label": "Bio-Medical Engineering"},
    {"value": "industrial", "label": "Industrial Engineering"},
    {"value": "design",     "label": "Design"},
    {"value": "agriculture","label": "Agricultural Engineering"},
]

VALID_BRANCH_PREFERENCES: List[str] = [b["value"] for b in BRANCH_PREFERENCES]

BRANCH_LABELS: Dict[str, str] = {b["value"]: b["label"] for b in BRANCH_PREFERENCES}
