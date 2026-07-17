"""Load and preprocess josaa_merged_2025.csv into a list of normalized
``Program`` records (Basic / 2025 mode only).

  Data source: josaa_merged_2025.csv — all institutes, all categories, all quotas,
               round-wise columns Opening_R1…R6 / Closing_R1…R6 for 2025.

  Opening Rank = MIN across Opening_R1…R6 (ignoring NaN, stripping 'P' suffix)
  Closing Rank = MAX across Closing_R1…R6 (same)

The extended multi-year dataset (merged_jee_cutoff_2018_2025.csv) and its loader
functions have been removed — all data now comes from josaa_merged_2025.csv.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from . import states
from .config import settings

DATA_PATH                = settings.resolved_data_path        # legacy Excel (kept for reference)
BASIC_MERGED_DATA_PATH   = settings.resolved_basic_merged_data_path

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
_TOP_5_IITS = {
    "Indian Institute of Technology Bombay",
    "Indian Institute of Technology Delhi",
    "Indian Institute of Technology Madras",
    "Indian Institute of Technology Kanpur",
    "Indian Institute of Technology Kharagpur",
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
    stable_cutoff: int = 0
    movement_ratio: float = 0.0
    jump_concentration: float = 0.0
    volatility_tag: str = "highly_stable"
    flag_round: Optional[int] = None
    is_top_iit: bool = False
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

# Round-wise column names present in josaa_merged_2025.csv
_OPENING_ROUND_COLS = [f"Opening_R{i}" for i in range(1, 7)]
_CLOSING_ROUND_COLS = [f"Closing_R{i}" for i in range(1, 7)]

# Identity columns that must be present in the merged CSV
_MERGED_KEY_COLS = ["Institute", "Academic Program Name", "Quota", "Seat Type", "Gender"]


def _split_col_by_suffix(col: pd.Series):
    """Split one round column into (regular, preparatory) numeric Series.

    JoSAA uses a trailing 'P' suffix (e.g. '151P', '2P') for Preparatory ranks
    issued to PwD candidates who missed the regular cutoff but scored ≥1 mark per
    subject.  These qualify candidates for a 1-year IIT preparatory/bridge course
    and are on a DIFFERENT rank scale — they must NOT be blended with regular
    Opening/Closing Rank statistics.

    Returns
    -------
    regular     : numeric Series — value present only for non-P cells, NaN otherwise
    preparatory : numeric Series — value present only for P-suffixed cells (suffix
                  stripped), NaN otherwise
    """
    s = col.astype(str).str.strip()
    # A Preparatory rank looks like one-or-more digits followed by a single P/p,
    # with nothing else.  This distinguishes "151P" from plain "151" or "nan".
    is_prep_mask = s.str.fullmatch(r'\d+[Pp]', na=False)

    regular     = pd.to_numeric(s.where(~is_prep_mask), errors="coerce")
    preparatory = pd.to_numeric(
        s.where(is_prep_mask).str.replace(r'[Pp]$', '', regex=True),
        errors="coerce",
    )
    return regular, preparatory


def compute_stable_and_volatility(closings_with_rounds: list[tuple[int, float]]) -> dict:
    """Compute stable cutoff and round-to-round volatility metrics.

    Parameters
    ----------
    closings_with_rounds : list of (round_num, rank) tuples, representing 2025 rounds.

    Returns
    -------
    dict with keys: stable_cutoff, movement_ratio, jump_concentration, tag, flag_round
    """
    # Clean the series — collect valid closing ranks keeping round order
    valid = [(r, float(c)) for r, c in closings_with_rounds if pd.notna(c) and c > 0]

    if not valid:
        return {
            "stable_cutoff": 0,
            "movement_ratio": 0.0,
            "jump_concentration": 0.0,
            "tag": "highly_stable",
            "flag_round": None
        }

    valid_ranks = [x[1] for x in valid]

    # Stable Cutoff:
    # If >= 4 valid rounds: median of the last 4 valid closings
    # Else: median of all valid closings
    if len(valid_ranks) >= 4:
        stable_cutoff = float(pd.Series(valid_ranks[-4:]).median())
    else:
        stable_cutoff = float(pd.Series(valid_ranks).median())

    if stable_cutoff == 0:
        stable_cutoff = valid_ranks[-1] if valid_ranks else 0.0

    # Consecutive round deltas
    deltas = []
    for i in range(len(valid) - 1):
        r_start, val_start = valid[i]
        r_end, val_end = valid[i+1]
        deltas.append((r_end, abs(val_end - val_start)))

    total_movement = sum(d[1] for d in deltas)

    if stable_cutoff > 0:
        movement_ratio = total_movement / stable_cutoff
    else:
        movement_ratio = 0.0

    # Jump concentration & max jump round detection
    max_single_jump = 0.0
    flag_round = None
    if deltas:
        max_item = max(deltas, key=lambda x: x[1])
        flag_round, max_single_jump = max_item

    if total_movement > 0:
        jump_concentration = max_single_jump / total_movement
    else:
        jump_concentration = 0.0

    # Classification
    # movement_ratio < 0.05 → Highly Stable (highly_stable)
    # movement_ratio < 0.20 and jump_concentration < 0.5 → Stable — Predictable Drift (stable_drift)
    # jump_concentration ≥ 0.5 and movement_ratio ≥ 0.20 → Volatile — Vacancy-Driven (volatile_vacancy)
    # else → Volatile — Erratic (volatile_erratic)
    if movement_ratio < 0.05:
        tag = "highly_stable"
    elif movement_ratio < 0.20 and jump_concentration < 0.5:
        tag = "stable_drift"
    elif jump_concentration >= 0.5 and movement_ratio >= 0.20:
        tag = "volatile_vacancy"
    else:
        tag = "volatile_erratic"

    return {
        "stable_cutoff": int(round(stable_cutoff)),
        "movement_ratio": float(movement_ratio),
        "jump_concentration": float(jump_concentration),
        "tag": tag,
        "flag_round": flag_round
    }


def compute_best_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """Derive Opening/Closing Rank, Preparatory ranks, and Volatility metrics from round-wise data.

    Returns a DataFrame with enriched fields:
      institute, program, quota, seat_type, gender,
      opening_rank, closing_rank, preparatory_opening_rank, preparatory_closing_rank,
      stable_cutoff, movement_ratio, jump_concentration, volatility_tag, flag_round
    """
    opening_cols = [c for c in _OPENING_ROUND_COLS if c in df.columns]
    closing_cols = [c for c in _CLOSING_ROUND_COLS if c in df.columns]
    if not opening_cols:
        raise ValueError("Merged CSV has no Opening_R* columns — wrong file?")
    if not closing_cols:
        raise ValueError("Merged CSV has no Closing_R* columns — wrong file?")

    out = df[_MERGED_KEY_COLS].copy()
    out.columns = ["institute", "program", "quota", "seat_type", "gender"]

    # Split every round column into regular and preparatory numeric values
    open_reg, open_prep, close_reg, close_prep = {}, {}, {}, {}
    for c in opening_cols:
        open_reg[c], open_prep[c] = _split_col_by_suffix(df[c])
    for c in closing_cols:
        close_reg[c], close_prep[c] = _split_col_by_suffix(df[c])

    # Regular ranks: MIN/MAX of non-P values only
    out["opening_rank"] = pd.DataFrame(open_reg).min(axis=1)
    out["closing_rank"] = pd.DataFrame(close_reg).max(axis=1)

    # Preparatory ranks: MIN/MAX of P-suffixed values only (kept strictly separate)
    out["preparatory_opening_rank"] = pd.DataFrame(open_prep).min(axis=1)
    out["preparatory_closing_rank"] = pd.DataFrame(close_prep).max(axis=1)

    # Calculate stable cutoff and volatility metrics row-by-row
    close_reg_df = pd.DataFrame(close_reg)
    round_nums = [int(c.split("_R")[-1]) for c in close_reg_df.columns]
    
    vol_results = [
        compute_stable_and_volatility(list(zip(round_nums, row)))
        for row in close_reg_df.itertuples(index=False)
    ]
    vol_df = pd.DataFrame(vol_results, index=df.index)

    out["stable_cutoff"] = vol_df["stable_cutoff"]
    out["movement_ratio"] = vol_df["movement_ratio"]
    out["jump_concentration"] = vol_df["jump_concentration"]
    out["volatility_tag"] = vol_df["tag"]
    out["flag_round"] = vol_df["flag_round"]

    # Pure-prep rows (all round values P-suffixed) have NaN regular ranks; drop them
    # from regular processing since they represent bridge-course seats, not normal
    # allotment seats.  The preparatory columns carry their data for future use.
    out = out.dropna(subset=["opening_rank", "closing_rank"])
    out["opening_rank"] = out["opening_rank"].astype(int)
    out["closing_rank"] = out["closing_rank"].astype(int)
    # Nullable int so NaN is allowed for non-preparatory rows
    out["preparatory_opening_rank"] = out["preparatory_opening_rank"].astype("Int64")
    out["preparatory_closing_rank"] = out["preparatory_closing_rank"].astype("Int64")
    return out


# ---------------------------------------------------------------------------
# Basic mode loader  (josaa_merged_2025.csv — all categories, all 6 rounds)
# Opening Rank = MIN(Opening_R1..R6), Closing Rank = MAX(Closing_R1..R6),
# computed fresh at runtime via compute_best_ranks() — raw CSV stays untouched.
# ---------------------------------------------------------------------------

def _load_basic_dataframe() -> pd.DataFrame:
    """Load the round-wise merged 2025 CSV and compute best ranks at runtime."""
    required_key_cols = _MERGED_KEY_COLS  # Institute, Academic Program Name, Quota, Seat Type, Gender
    df = pd.read_csv(BASIC_MERGED_DATA_PATH)

    missing = [c for c in required_key_cols if c not in df.columns]
    if missing:
        raise ValueError(f"josaa_merged_2025.csv missing expected columns: {missing}")

    # Compute Opening/Closing rank from round-wise data — never reads pre-calculated values.
    return compute_best_ranks(df)


# Program name keywords that identify non-engineering programs to exclude.
_EXCLUDED_PROGRAM_KEYWORDS = ("planning", "architecture")


@lru_cache(maxsize=1)
def load_programs_basic() -> List[Program]:
    df = _load_basic_dataframe()
    programs: List[Program] = []
    for row in df.itertuples(index=False):
        institute = str(row.institute).strip()
        # Skip School of Planning & Architecture institutes entirely
        if "planning" in institute.lower():
            continue
        itype = _classify_institute_type(institute)
        full = str(row.program).strip()
        # Skip Planning and Architecture programs — they are not standard
        # engineering/technology programs and should not appear anywhere.
        if any(kw in full.lower() for kw in _EXCLUDED_PROGRAM_KEYWORDS):
            continue
        short, degree = _clean_branch(full)
        seat_type = str(getattr(row, "seat_type", "OPEN")).strip()
        flag_r = getattr(row, "flag_round", None)
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
                is_top_iit=(itype == "IIT" and institute in _TOP_5_IITS),
                stable_cutoff=int(row.stable_cutoff),
                movement_ratio=float(row.movement_ratio),
                jump_concentration=float(row.jump_concentration),
                volatility_tag=str(row.volatility_tag),
                flag_round=None if pd.isna(flag_r) else int(flag_r),
                tags=states.classify_branch(full),
            )
        )
    return programs


# ---------------------------------------------------------------------------
# REMOVED: Extended mode loader (merged_jee_cutoff_2018_2025.csv, 2018-2025).
# The following functions were fully dependent on the multi-year extended dataset
# and have been deleted:
#   - _load_full_extended_dataframe()
#   - _load_extended_dataframe()
#   - get_extended_history_index()
#   - load_programs_extended()
# ---------------------------------------------------------------------------

# TODO (reworkable): get_program_history() currently returns only {2025: closing_rank}
# in basic mode — a single data point.  Once Stable/Volatile Cutoff metrics are
# implemented using round-wise columns from josaa_merged_2025.csv, this function
# should be replaced by a round-based history derived from Closing_R1…R6.
def get_program_history(prog: "Program", data_mode: str = "basic") -> Dict[int, int]:
    """Return closing rank history keyed by year.

    Currently returns only 2025 data (one point).  Will be reworked to return
    round-wise closing ranks from josaa_merged_2025.csv as a volatility proxy.
    """
    return {2025: prog.closing_rank}


# ---------------------------------------------------------------------------
# Public entry point — always returns basic (2025) programs.
# ---------------------------------------------------------------------------

def load_programs(data_mode: str = "basic") -> List[Program]:
    """Return the cached program list.  Extended mode has been removed; data_mode
    is accepted for API compatibility but always loads the 2025 basic dataset.
    """
    # TODO (reworkable): remove the data_mode parameter entirely once all callers
    # have been updated to stop passing it.
    return load_programs_basic()


# ---------------------------------------------------------------------------
# Advantage lookup indices — precomputed once from the 2025 basic dataset.
# TODO (reworkable): remove the data_mode parameter from both functions once
# all callers have been updated (they currently always pass "basic").
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
    print(f"HS advantage entries:     {len(home_state_advantage_index('basic'))}")
    print(f"Female advantage entries: {len(female_seat_advantage_index('basic'))}")
