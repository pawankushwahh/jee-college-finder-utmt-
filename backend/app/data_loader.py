"""Load and preprocess the JEE cutoff workbook into a list of normalized
``Program`` records. The workbook is parsed once and cached.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Set, Tuple

import pandas as pd

from . import states
from .config import settings

DATA_PATH = settings.resolved_data_path

# Premier / older institutes get a small brand bonus (matters for the "mba" and
# "undecided" goals and as a tie-breaker everywhere).
_OLD_IITS = {
    "Indian Institute of Technology Bombay",
    "Indian Institute of Technology Delhi",
    "Indian Institute of Technology Madras",
    "Indian Institute of Technology Kanpur",
    "Indian Institute of Technology Kharagpur",
    "Indian Institute of Technology Roorkee",
    "Indian Institute of Technology Guwahati",
    "Indian Institute of Technology (BHU) Varanasi",
}
_TOP_NITS = {
    "National Institute of Technology, Tiruchirappalli",
    "National Institute of Technology, Warangal",
    "National Institute of Technology Karnataka, Surathkal",
    "National Institute of Technology Calicut",
    "Motilal Nehru National Institute of Technology Allahabad",
    "Visvesvaraya National Institute of Technology, Nagpur",
    "Sardar Vallabhbhai National Institute of Technology, Surat",
    "Malaviya National Institute of Technology Jaipur",
}


@dataclass(frozen=True)
class Program:
    institute: str
    institute_type: str  # IIT / NIT / IIIT / GFTI
    institute_state: str
    exam: str  # "advanced" (IITs) or "mains" (everything else)
    branch: str  # cleaned short branch name
    branch_full: str  # original academic program name
    degree: str  # e.g. "Bachelor of Technology"
    quota: str  # AI / HS / OS / GO / JK / LA
    gender_pool: str  # "neutral" or "female"
    opening_rank: int
    closing_rank: int
    brand_score: float
    tags: Set[str] = field(default_factory=set)


def _classify_institute_type(name: str) -> str:
    low = name.lower()
    if "indian institute of technology" in low and "information" not in low:
        return "IIT"
    if "national institute of technology" in low:
        return "NIT"
    if "information technology" in low:
        return "IIIT"
    return "GFTI"


def _brand_score(name: str, itype: str) -> float:
    if itype == "IIT":
        return 1.0 if name in _OLD_IITS else 0.88
    if itype == "NIT":
        return 0.78 if name in _TOP_NITS else 0.68
    if itype == "IIIT":
        return 0.6
    return 0.5


def _clean_branch(program: str) -> tuple[str, str]:
    """Split an academic program name into (short branch, degree)."""
    program = str(program).strip()
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", program)
    if m:
        short = m.group(1).strip()
        inside = m.group(2)
        # inside looks like "4 Years, Bachelor of Technology"
        degree = inside.split(",")[-1].strip()
        return short, degree
    return program, ""


def _normalize_gender(value: str) -> str:
    return "female" if "female" in str(value).lower() else "neutral"


_COLUMN_RENAME = {
    "Institute": "institute",
    "Academic Program Name": "program",
    "Quota": "quota",
    "Seat Type": "seat_type",
    "Gender": "gender",
    "Opening Rank": "opening_rank",
    "Closing Rank": "closing_rank",
}


def _load_dataframe() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, engine="openpyxl")
    missing = [c for c in _COLUMN_RENAME if c not in df.columns]
    if missing:
        raise ValueError(f"Cutoff file missing expected columns: {missing}")
    df = df.rename(columns=_COLUMN_RENAME)
    df = df.dropna(subset=["institute", "program", "opening_rank", "closing_rank"])
    df["opening_rank"] = pd.to_numeric(df["opening_rank"], errors="coerce")
    df["closing_rank"] = pd.to_numeric(df["closing_rank"], errors="coerce")
    df = df.dropna(subset=["opening_rank", "closing_rank"])
    return df


@lru_cache(maxsize=1)
def load_programs() -> List[Program]:
    df = _load_dataframe()
    programs: List[Program] = []
    for row in df.itertuples(index=False):
        institute = str(row.institute).strip()
        itype = _classify_institute_type(institute)
        full = str(row.program).strip()
        short, degree = _clean_branch(full)
        programs.append(
            Program(
                institute=institute,
                institute_type=itype,
                institute_state=states.get_institute_state(institute),
                exam="advanced" if itype == "IIT" else "mains",
                branch=short,
                branch_full=full,
                degree=degree,
                quota=str(row.quota).strip(),
                gender_pool=_normalize_gender(row.gender),
                opening_rank=int(row.opening_rank),
                closing_rank=int(row.closing_rank),
                brand_score=_brand_score(institute, itype),
                tags=states.classify_branch(full),
            )
        )
    return programs


# ---------------------------------------------------------------------------
# Advantage lookup indices.
#
# Both are precomputed once (at first access, then cached) so the recommender
# can attach a "why" to each option with an O(1) dict lookup instead of
# re-scanning the dataset on every request.
# ---------------------------------------------------------------------------

# A program is uniquely identified (across quota / gender pools) by this key.
ProgramKey = Tuple[str, str, str]  # (institute, branch_full, exam)


@lru_cache(maxsize=1)
def home_state_advantage_index() -> Dict[Tuple[str, str, str, str], int]:
    """Map an HS seat to the ranks it saves vs the equivalent open-pool seat.

    For each (institute, branch_full, exam, gender_pool), compare the Home-State
    (HS) row's closing rank against the same program's Other-State (OS) row
    (falling back to All-India (AI) when there is no OS row). The advantage is
    ``other_closing - hs_closing`` and is only stored when positive (i.e. the HS
    quota genuinely lets a candidate in at a worse rank than they'd need
    otherwise).

    Key: (institute, branch_full, exam, gender_pool) -> ranks saved.
    """
    # group -> {quota: closing_rank}
    groups: Dict[Tuple[str, str, str, str], Dict[str, int]] = defaultdict(dict)
    for prog in load_programs():
        key = (prog.institute, prog.branch_full, prog.exam, prog.gender_pool)
        # Keep the most generous (largest) closing rank per quota if duplicated.
        prev = groups[key].get(prog.quota)
        if prev is None or prog.closing_rank > prev:
            groups[key][prog.quota] = prog.closing_rank

    index: Dict[Tuple[str, str, str, str], int] = {}
    for key, by_quota in groups.items():
        hs = by_quota.get("HS")
        if hs is None:
            continue
        other = by_quota.get("OS")
        if other is None:
            other = by_quota.get("AI")
        if other is None:
            continue
        advantage = other - hs
        if advantage > 0:
            index[key] = advantage
    return index


@lru_cache(maxsize=1)
def female_seat_advantage_index() -> Dict[Tuple[str, str, str, str], int]:
    """Map a Female-only seat to how many ranks later it closes vs the neutral pool.

    For each (institute, branch_full, exam, quota), compare the Female-only
    closing rank against the Gender-Neutral closing rank of the same program.
    The advantage is ``female_closing - neutral_closing`` and is only stored
    when positive (the female pool closes at a later/worse rank, so a female
    applicant gets a cushion).

    Key: (institute, branch_full, exam, quota) -> ranks of extra cushion.
    """
    groups: Dict[Tuple[str, str, str, str], Dict[str, int]] = defaultdict(dict)
    for prog in load_programs():
        key = (prog.institute, prog.branch_full, prog.exam, prog.quota)
        prev = groups[key].get(prog.gender_pool)
        if prev is None or prog.closing_rank > prev:
            groups[key][prog.gender_pool] = prog.closing_rank

    index: Dict[Tuple[str, str, str, str], int] = {}
    for key, by_pool in groups.items():
        female = by_pool.get("female")
        neutral = by_pool.get("neutral")
        if female is None or neutral is None:
            continue
        advantage = female - neutral
        if advantage > 0:
            index[key] = advantage
    return index


if __name__ == "__main__":  # pragma: no cover - manual sanity check
    progs = load_programs()
    print(f"Loaded {len(progs)} programs")
    print(progs[0])
    print(f"HS advantage entries: {len(home_state_advantage_index())}")
    print(f"Female advantage entries: {len(female_seat_advantage_index())}")
