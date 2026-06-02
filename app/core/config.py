from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Application ──────────────────────────────────────────
    app_name: str = "CloudGodPlatform"
    env: str = "local"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    # ── Auth / JWT ───────────────────────────────────────────
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # ── Database ─────────────────────────────────────────────
    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/cloudgod"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── AWS / LocalStack ─────────────────────────────────────
    aws_region: str = "ap-south-1"
    aws_endpoint_url: str | None = None
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    s3_bucket: str = "cloud-god-docs"
    sqs_queue_url: str = ""

    # ── LLM / Embeddings ─────────────────────────────────────
    openai_api_key: str = ""
    ollama_base_url: str = "http://ollama:11434"
    llm_provider: str = "ollama"
    embedding_model: str = "bge-small"
    chat_model: str = "llama3.1"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Export AWS credentials to environment variables for boto3 compatibility in local dev
if "AWS_ACCESS_KEY_ID" not in os.environ:
    os.environ["AWS_ACCESS_KEY_ID"] = settings.aws_access_key_id
if "AWS_SECRET_ACCESS_KEY" not in os.environ:
    os.environ["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key
