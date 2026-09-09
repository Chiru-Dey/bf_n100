from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from the environment."""

    db_path: Path
    raw_data_dir: Path
    supporting_data_dir: Path
    output_dir: Path
    reports_dir: Path
    config_dir: Path
    log_level: str
    validate_urls: bool


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings(
        db_path=Path(getenv("DB_PATH", "data/nifty100.db")),
        raw_data_dir=Path(getenv("RAW_DATA_DIR", "data/raw")),
        supporting_data_dir=Path(getenv("SUPPORTING_DATA_DIR", "data/supporting")),
        output_dir=Path(getenv("OUTPUT_DIR", "output")),
        reports_dir=Path(getenv("REPORTS_DIR", "reports")),
        config_dir=Path(getenv("CONFIG_DIR", "config")),
        log_level=getenv("LOG_LEVEL", "INFO"),
        validate_urls=getenv("VALIDATE_URLS", "false").lower() == "true",
    )
