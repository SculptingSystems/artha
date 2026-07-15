from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    llm_provider: str = "anthropic"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    redis_url: str = "redis://localhost:6379"
    database_url: str = "postgresql://artha:artha@localhost:5432/artha"
    news_api_key: str = ""

    log_level: str = "INFO"
    max_candidates: int = 500
    cache_ttl_seconds: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
