"""Pytest configuration — set dummy environment variables before any app imports."""

import os

# These must be set BEFORE any app module is imported,
# because get_settings() will read them on first call.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-000000")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("TIMEZONE", "America/Bogota")
