"""Data loader for COMEDK 2025 cutoffs."""

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
        return float(val.strip())
    except ValueError:
        return None

def load_comedk_programs() -> List[dict]:
    """Load COMEDK 2025 cutoff data."""
    csv_path = _DATA_DIR / "comedk_2025.csv"
    if not csv_path.exists():
        logger.error(f"COMEDK data file not found: {csv_path}")
        return []

    programs = []
    
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            institute = row.get("Institute", "").strip()
            program = row.get("Academic Program Name", "").strip()
            quota = row.get("Quota", "").strip()
            
            if not institute or not program or not quota:
                continue

            # Extract max closing rank across all rounds to represent the true cutoff
            closing_ranks = []
            for r in range(1, 7):
                val = _safe_float(row.get(f"Closing_R{r}"))
                if val is not None:
                    closing_ranks.append(val)
                    
            if not closing_ranks:
                continue
                
            cutoff_rank = max(closing_ranks)
            
            programs.append({
                "institute": institute,
                "program": program,
                "quota": quota,
                "cutoff_rank": cutoff_rank
            })
            
    return programs

_cached_programs = None

def get_programs() -> List[dict]:
    """Cached accessor for COMEDK programs."""
    global _cached_programs
    if _cached_programs is None:
        _cached_programs = load_comedk_programs()
    return _cached_programs
