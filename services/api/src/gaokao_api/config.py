from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./services/api/gaokao_mvp.db"
    ark_api_key: str | None = None
    ark_model: str = "minimax-m2.5"
    ark_instant_model: str | None = None
    ark_deepthink_model: str | None = None
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    enable_live_llm: bool = False
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

    @property
    def effective_instant_model(self) -> str:
        return self.ark_instant_model or self.ark_model

    @property
    def effective_deepthink_model(self) -> str:
        return self.ark_deepthink_model or self.ark_model


settings = Settings()
