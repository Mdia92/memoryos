"""Application settings, loaded from environment / .env at the repo root."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "confidence_policy.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Qwen via Alibaba Cloud Model Studio (DashScope OpenAI-compatible mode)
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_primary_model: str = "qwen-plus"
    qwen_fallback_model: str = "qwen-turbo"
    qwen_embedding_model: str = "text-embedding-v3"

    database_url: str = "postgresql+asyncpg://memoryos:memoryos@localhost:5433/memoryos"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_policy() -> dict:
    """confidence_policy.yaml — behavior changes through configuration, not redeployment."""
    with open(POLICY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
