"""Data loader for KCET 2025 cutoffs."""

import csv
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent / "data"

def _safe_float(val: str) -> Optional[float]:
    if not val or not val.strip():
        return None
    try:
        # Remove commas or spaces
        clean_val = val.replace(",", "").strip()
        return float(clean_val)
    except ValueError:
        return None

def load_kcet_programs() -> List[dict]:
    """Load KCET 2025 cutoff data from CSV."""
    csv_path = _DATA_DIR / "kcet_2025.csv"
    if not csv_path.exists():
        logger.error(f"KCET data file not found: {csv_path}")
        return []

    programs = []
    
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Try to resolve keys case-insensitively or dynamically
            keys = {k.lower(): k for k in row.keys()}
            
            inst_key = (
                keys.get("college_name") or 
                keys.get("institute") or 
                "Institute"
            )
            prog_key = (
                keys.get("course_name") or 
                keys.get("academic program name") or 
                keys.get("program") or 
                "Academic Program Name"
            )
            quota_key = (
                keys.get("category") or 
                keys.get("quota") or 
                "Quota"
            )
            
            institute = row.get(inst_key, "").strip()
            program = row.get(prog_key, "").strip()
            quota = row.get(quota_key, "").strip()
            
            if not institute or not program:
                continue

            # Determine the cutoff rank column
            cutoff_rank = None
            cutoff_key = (
                keys.get("closing_rank") or 
                keys.get("cutoff_rank") or 
                keys.get("cutoff") or 
                "Cutoff_Rank"
            )
            if cutoff_key in row:
                cutoff_rank = _safe_float(row[cutoff_key])
            
            if cutoff_rank is None:
                # Try round-wise closing columns if available
                closing_ranks = []
                for r in range(1, 7):
                    r_key = keys.get(f"closing_r{r}")
                    if r_key and r_key in row:
                        val = _safe_float(row[r_key])
                        if val is not None:
                            closing_ranks.append(val)
                if closing_ranks:
                    cutoff_rank = max(closing_ranks)

            if cutoff_rank is None:
                continue
            
            programs.append({
                "institute": institute,
                "program": program,
                "quota": quota,
                "cutoff_rank": cutoff_rank
            })
            
    return programs

_cached_programs = None

def get_programs() -> List[dict]:
    """Cached accessor for KCET programs."""
    global _cached_programs
    if _cached_programs is None:
        _cached_programs = load_kcet_programs()
    return _cached_programs
