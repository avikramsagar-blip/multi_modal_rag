"""
core/config.py

Loads all environment variables required by the application.
Create a .env file in the project root with the values below.

Required:
    CHROMA_API_KEY      — Chroma Cloud API key
    CHROMA_TENANT       — Chroma Cloud tenant name
    CHROMA_DATABASE     — Chroma Cloud database name
    GROK_API_KEY        — Grok API key
    GROK_API_BASE_URL   — Grok API base URL (default provided)

Optional:
    LOG_LEVEL           — DEBUG | INFO | WARNING (default: INFO)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Add it to your .env file."
        )
    return value


def _get_with_fallback(primary_key: str, fallback_key: str) -> str:
    value = os.getenv(primary_key) or os.getenv(fallback_key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{primary_key}' is not set. "
            f"(Accepted fallback: '{fallback_key}'). Add it to your .env file."
        )
    return value


@dataclass(frozen=True)
class Settings:
    chroma_api_key: str = field(default_factory=lambda: _require("CHROMA_API_KEY"))
    chroma_tenant: str = field(default_factory=lambda: _require("CHROMA_TENANT"))
    chroma_database: str = field(default_factory=lambda: _require("CHROMA_DATABASE"))

    grok_api_key: str = field(
        default_factory=lambda: _get_with_fallback("GROK_API_KEY", "GROQ_API_KEY")
    )
    grok_api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "GROK_API_BASE_URL",
            os.getenv("GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"),
        )
    )
    grok_model: str = field(
        default_factory=lambda: os.getenv(
            "GROK_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        )
    )

    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )


# Single shared instance — import `settings` everywhere
settings = Settings()
