"""Static configuration for the backend API service.

All deployment-specific values (CORS origins, data file location, etc.) are
defined as constants in this file to run cleanly without environment variables.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings:
    # Comma-separated list of allowed frontend origins, or "*" for any.
    cors_origins: str = "*"

    # Path to the basic cutoff workbook (legacy, kept for reference).
    data_path: str = "app/disha/data/JEE_2025_Cutoffs.xlsx"

    # Path to the round-wise merged CSV for Basic (2025) mode.
    # Has columns Opening_R1..Closing_R6; Opening/Closing Rank are
    # computed at runtime as MIN/MAX across rounds.
    basic_merged_data_path: str = "app/disha/data/josaa_merged_2025.csv"


    # Active data mode: always "basic" (2025 round-wise merged CSV).
    # Extended mode has been removed — this setting is kept for API compatibility.
    data_mode: str = "basic"

    # ── Curation: how many cards each bucket shows by default ─────────────
    # Measured against the 2025 JoSAA set, the uncapped engine returned 118
    # options at Mains rank 1, 489 at rank 20,000 and 307 at rank 50,000 — a
    # data dump rather than a recommendation.  These caps bound the default
    # "all" response only: every eligible programme is still counted in
    # ``total_by_type[...]["total_attainable"]`` and still reachable by asking
    # for a single bucket (``bucket=safe|target|dream``), which is returned
    # uncapped.  Ordering plus a cap does the curation; nothing is deleted.
    cap_target: int = 25
    cap_reach: int = 15
    cap_safe: int = 15

    # Max programmes from a single institute inside one bucket's shown list.
    # Ordering by interest score alone gave a Mains rank-1 student three cards
    # from Surathkal and three from Warangal inside the first twenty; students
    # want a shortlist of colleges, not one college's prospectus.  The
    # allowance is relaxed one seat at a time when a bucket cannot otherwise
    # fill, so diversity never costs the student options.
    max_per_institute: int = 2

    # ── Top-rank mode ─────────────────────────────────────────────────────
    # For exceptional ranks every programme lands in Safe (at Mains rank 1:
    # 118 Safe, 0 Target, 0 Dream, all at 100 % probability), so the
    # three-bucket framing carries no signal at all.  Detected from the bucket
    # counts rather than a hardcoded rank, because the rank scale differs
    # wildly per seat category — an SC rank-500 student has 546 eligible
    # options where an OPEN rank-500 student has 124, and ST is exhausted by
    # rank 20,000 where OPEN peaks.  Any fixed rank threshold would be wrong
    # for most categories.
    top_rank_cap: int = 25

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["*"]

    @property
    def resolved_data_path(self) -> Path:
        p = Path(self.data_path)
        return p if p.is_absolute() else _PROJECT_ROOT / p

    @property
    def resolved_basic_merged_data_path(self) -> Path:
        p = Path(self.basic_merged_data_path)
        return p if p.is_absolute() else _PROJECT_ROOT / p


    @property
    def resolved_extended_data_path(self) -> Path:
        """REMOVED — returns a non-existent path; kept only to avoid AttributeError
        in any code not yet updated to stop referencing this property.
        """
        return Path("app/disha/data/merged_jee_cutoff_2018_2025.csv")  # no longer used


settings = Settings()

