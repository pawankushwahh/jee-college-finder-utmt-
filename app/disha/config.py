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

