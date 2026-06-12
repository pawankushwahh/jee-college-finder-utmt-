"""Environment-based configuration for the backend API service.

All deployment-specific values (CORS origins, data file location, etc.) are
read from environment variables (optionally via a ``.env`` file), so the same
code runs unchanged in development, staging and production.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Comma-separated list of allowed frontend origins, or "*" for any.
    # The API is public and read-only (no cookies / credentials), so a wildcard
    # is safe and lets the portal work from file://, Live Server previews, etc.
    cors_origins: str = "*"

    # Path to the cutoff workbook. Relative paths resolve against backend/.
    data_path: str = "data/JEE_2025_Cutoffs.xlsx"

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["*"]

    @property
    def resolved_data_path(self) -> Path:
        p = Path(self.data_path)
        return p if p.is_absolute() else _BACKEND_ROOT / p


settings = Settings()
