"""Load and preprocess the JEE cutoff workbook into a list of normalized
``Program`` records. The workbook is parsed once and cached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Set

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


if __name__ == "__main__":  # pragma: no cover - manual sanity check
    progs = load_programs()
    print(f"Loaded {len(progs)} programs")
    print(progs[0])
