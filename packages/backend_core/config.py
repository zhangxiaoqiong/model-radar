"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MySQL
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "model_radar"

    # Admin auth (V1a: single token; RBAC deferred)
    admin_api_token: str = ""

    # Artificial Analysis
    aa_api_key: str = ""
    aa_base_url: str = "https://artificialanalysis.ai/api/v2"

    # Raw snapshot storage
    snapshot_dir: str = "data/raw"

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
