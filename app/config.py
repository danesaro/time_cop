"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from .env file or environment variables."""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Telegram Bot API token")

    # Database (Supabase PostgreSQL)
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")

    # AI
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API key")

    # App
    TIMEZONE: str = Field(default="America/Bogota", description="Application timezone")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Webhook (optional – leave empty for polling mode)
    WEBHOOK_URL: Optional[str] = Field(default=None, description="Public HTTPS URL for Telegram webhook")

    # Connection pool
    DB_POOL_MIN_SIZE: int = Field(default=2, description="Minimum DB pool connections")
    DB_POOL_MAX_SIZE: int = Field(default=10, description="Maximum DB pool connections")

    # Rate limiting
    RATE_LIMIT_MESSAGES: int = Field(default=30, description="Max messages per user per minute")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @property
    def is_webhook_mode(self) -> bool:
        """Return True if a webhook URL is configured."""
        return bool(self.WEBHOOK_URL)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Created on first call."""
    return Settings()
