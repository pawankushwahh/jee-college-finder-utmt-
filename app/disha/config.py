"""Environment-based configuration for the backend API service.

All deployment-specific values (CORS origins, data file location, etc.) are
read from environment variables (optionally via a ``.env`` file), so the same
code runs unchanged in development, staging and production.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Comma-separated list of allowed frontend origins, or "*" for any.
    cors_origins: str = "*"

    # Path to the basic cutoff workbook (sir-provided, OPEN only, 2025).
    # Relative paths resolve against project root.
    data_path: str = "app/disha/data/JEE_2025_Cutoffs.xlsx"

    # Path to the extended merged CSV (all categories, 2018–2025).
    extended_data_path: str = "app/disha/data/merged_jee_cutoff_2018_2025.csv"

    # Active data mode: "basic" uses only the Excel file (OPEN seats, 2025),
    # "extended" uses the merged CSV (all categories, 2018-2025).
    # This is the server-side default; users can override via the UI toggle
    # if allow_user_data_toggle is True.
    data_mode: str = "basic"

    # When True, the frontend shows a Data Source toggle so users can switch
    # between basic and extended mode themselves. Set to False to lock the
    # mode to whatever data_mode is set above (useful for classroom/demo use).
    allow_user_data_toggle: bool = True

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["*"]

    @property
    def resolved_data_path(self) -> Path:
        p = Path(self.data_path)
        return p if p.is_absolute() else _PROJECT_ROOT / p

    @property
    def resolved_extended_data_path(self) -> Path:
        p = Path(self.extended_data_path)
        return p if p.is_absolute() else _PROJECT_ROOT / p


settings = Settings()
