"""Load and preprocess the JEE cutoff workbook/CSV into a list of normalized
``Program`` records. Supports two data modes:

  - "basic"    : reads JEE_2025_Cutoffs.xlsx (OPEN seats only, 2025)
  - "extended" : reads merged_jee_cutoff_2018_2025.csv (all categories, 2018-2025,
                 filtered to the last allocation round of 2025)

Both datasets are cached separately so the server can preload them at startup
and serve either on demand.
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

DATA_PATH          = settings.resolved_data_path
EXTENDED_DATA_PATH = settings.resolved_extended_data_path

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
    seat_type: str  # OPEN / OBC-NCL / SC / ST / EWS / OPEN (PwD) / etc.
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
    v = str(value).lower().strip()
    if "female" in v or v == "f":
        return "female"
    return "neutral"


_COLUMN_RENAME = {
    "Institute": "institute",
    "Academic Program Name": "program",
    "Quota": "quota",
    "Seat Type": "seat_type",
    "Gender": "gender",
    "Opening Rank": "opening_rank",
    "Closing Rank": "closing_rank",
}


# ---------------------------------------------------------------------------
# Basic mode loader  (Excel, OPEN only, 2025)
# ---------------------------------------------------------------------------

def _load_basic_dataframe() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, engine="openpyxl")
    missing = [c for c in _COLUMN_RENAME if c not in df.columns]
    if missing:
        raise ValueError(f"Cutoff file missing expected columns: {missing}")
    df = df.rename(columns=_COLUMN_RENAME)
    df = df.dropna(subset=["institute", "program", "opening_rank", "closing_rank"])
    df["opening_rank"] = pd.to_numeric(df["opening_rank"], errors="coerce")
    df["closing_rank"] = pd.to_numeric(df["closing_rank"], errors="coerce")
    df = df.dropna(subset=["opening_rank", "closing_rank"])
    # Basic file already has only OPEN rows; ensure the column exists.
    if "seat_type" not in df.columns:
        df["seat_type"] = "OPEN"
    return df


@lru_cache(maxsize=1)
def load_programs_basic() -> List[Program]:
    df = _load_basic_dataframe()
    programs: List[Program] = []
    for row in df.itertuples(index=False):
        institute = str(row.institute).strip()
        itype = _classify_institute_type(institute)
        full = str(row.program).strip()
        short, degree = _clean_branch(full)
        seat_type = str(getattr(row, "seat_type", "OPEN")).strip()
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
                seat_type=seat_type,
                opening_rank=int(row.opening_rank),
                closing_rank=int(row.closing_rank),
                brand_score=_brand_score(institute, itype),
                tags=states.classify_branch(full),
            )
        )
    return programs


# ---------------------------------------------------------------------------
# Extended mode loader  (merged CSV, all categories, 2018-2025)
# Filters to the LAST available round of 2025 per institute-program-quota-
# seat_type-gender combination — that is the final JoSAA allocation cutoff.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_full_extended_dataframe() -> pd.DataFrame:
    df = pd.read_csv(EXTENDED_DATA_PATH)
    missing = [c for c in _COLUMN_RENAME if c not in df.columns]
    if missing:
        raise ValueError(f"Extended CSV missing expected columns: {missing}")
    df = df.rename(columns=_COLUMN_RENAME)
    df = df.dropna(subset=["institute", "program", "opening_rank", "closing_rank"])
    df["opening_rank"] = pd.to_numeric(df["opening_rank"], errors="coerce")
    df["closing_rank"] = pd.to_numeric(df["closing_rank"], errors="coerce")
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce").fillna(2025).astype(int)
    else:
        df["Year"] = 2025
    df = df.dropna(subset=["opening_rank", "closing_rank"])
    return df


def _load_extended_dataframe() -> pd.DataFrame:
    df = _load_full_extended_dataframe()
    # Keep only 2025 data.
    if "Year" in df.columns:
        df = df[df["Year"] == 2025]

    # For each unique (institute, program, quota, seat_type, gender) keep the
    # row from the highest round number — that is the final closing rank.
    group_keys = ["institute", "program", "quota", "seat_type", "gender"]
    if "Round" in df.columns:
        df["_round"] = pd.to_numeric(df["Round"], errors="coerce").fillna(0)
        idx = df.groupby(group_keys)["_round"].idxmax()
        df = df.loc[idx].drop(columns=["_round"])

    return df


@lru_cache(maxsize=1)
def get_extended_history_index() -> Dict[Tuple[str, str, str, str, str], Dict[int, int]]:
    """Build a mapping of (institute, program_full, quota, seat_type, gender) -> {year: closing_rank}."""
    df = _load_full_extended_dataframe()
    group_keys = ["institute", "program", "quota", "seat_type", "gender", "Year"]
    if "Round" in df.columns:
        df["_round"] = pd.to_numeric(df["Round"], errors="coerce").fillna(0)
        # Sort by round so that tail() or last() gets the highest round
        df_sorted = df.sort_values("_round")
        # Drop duplicates keeping the last (highest round)
        df_final = df_sorted.drop_duplicates(subset=group_keys, keep="last")
    else:
        df_final = df
    
    history: Dict[Tuple[str, str, str, str, str], Dict[int, int]] = defaultdict(dict)
    for row in df_final.itertuples(index=False):
        key = (
            str(row.institute).strip(),
            str(row.program).strip(),
            str(row.quota).strip() if pd.notna(row.quota) else "AI",
            str(row.seat_type).strip() if pd.notna(row.seat_type) else "OPEN",
            _normalize_gender(row.gender)
        )
        history[key][int(row.Year)] = int(row.closing_rank)
    return history


def get_program_history(prog: Program, data_mode: str) -> Dict[int, int]:
    """Return historical closing ranks by year for the program."""
    if data_mode == "extended":
        history_index = get_extended_history_index()
        key = (prog.institute, prog.branch_full, prog.quota, prog.seat_type, prog.gender_pool)
        hist = history_index.get(key, {})
        if hist:
            # Sort the history by year and return it
            return {y: hist[y] for y in sorted(hist.keys())}
    return {2025: prog.closing_rank}


@lru_cache(maxsize=1)
def load_programs_extended() -> List[Program]:
    df = _load_extended_dataframe()
    programs: List[Program] = []
    for row in df.itertuples(index=False):
        institute = str(row.institute).strip()
        itype = _classify_institute_type(institute)
        full = str(row.program).strip()
        short, degree = _clean_branch(full)
        seat_type = str(row.seat_type).strip() if pd.notna(row.seat_type) else "OPEN"
        quota_val = str(row.quota).strip() if pd.notna(row.quota) else "AI"
        programs.append(
            Program(
                institute=institute,
                institute_type=itype,
                institute_state=states.get_institute_state(institute),
                exam="advanced" if itype == "IIT" else "mains",
                branch=short,
                branch_full=full,
                degree=degree,
                quota=quota_val,
                gender_pool=_normalize_gender(row.gender),
                seat_type=seat_type,
                opening_rank=int(row.opening_rank),
                closing_rank=int(row.closing_rank),
                brand_score=_brand_score(institute, itype),
                tags=states.classify_branch(full),
            )
        )
    return programs


# ---------------------------------------------------------------------------
# Public entry point — dispatches by data_mode string.
# ---------------------------------------------------------------------------

def load_programs(data_mode: str = "basic") -> List[Program]:
    """Return the cached program list for the given data_mode."""
    if data_mode == "extended":
        return load_programs_extended()
    return load_programs_basic()


# ---------------------------------------------------------------------------
# Advantage lookup indices.
# Both are precomputed once and cached per data_mode.
# ---------------------------------------------------------------------------

# A program is uniquely identified (across quota / gender pools) by this key.
ProgramKey = Tuple[str, str, str]  # (institute, branch_full, exam)


@lru_cache(maxsize=2)
def home_state_advantage_index(data_mode: str = "basic") -> Dict[Tuple[str, str, str, str], int]:
    """Map an HS seat to the ranks it saves vs the equivalent open-pool seat.

    Key: (institute, branch_full, exam, gender_pool) -> ranks saved.
    """
    groups: Dict[Tuple[str, str, str, str], Dict[str, int]] = defaultdict(dict)
    for prog in load_programs(data_mode):
        key = (prog.institute, prog.branch_full, prog.exam, prog.gender_pool)
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


@lru_cache(maxsize=2)
def female_seat_advantage_index(data_mode: str = "basic") -> Dict[Tuple[str, str, str, str], int]:
    """Map a Female-only seat to how many ranks later it closes vs the neutral pool.

    Key: (institute, branch_full, exam, quota) -> ranks of extra cushion.
    """
    groups: Dict[Tuple[str, str, str, str], Dict[str, int]] = defaultdict(dict)
    for prog in load_programs(data_mode):
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
    basic = load_programs("basic")
    print(f"Basic mode:    {len(basic)} programs")
    ext = load_programs("extended")
    print(f"Extended mode: {len(ext)} programs")
    print(f"Extended HS advantage entries:     {len(home_state_advantage_index('extended'))}")
    print(f"Extended Female advantage entries: {len(female_seat_advantage_index('extended'))}")
