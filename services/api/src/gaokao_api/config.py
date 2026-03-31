from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./services/api/gaokao_mvp.db"
    mimo_api_key: str | None = None
    mimo_model: str = "mimo-v2-flash"
    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    knowledge_root: str = "packages/knowledge/data"
    province: str = "henan"
    target_year: int = 2026

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[4]

    @property
    def knowledge_path(self) -> Path:
        root = Path(self.knowledge_root)
        return root if root.is_absolute() else self.repo_root / root


settings = Settings()
