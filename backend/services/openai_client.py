"""
services/openai_client.py — Shared OpenAI/OpenRouter Client Factory
====================================================================
Centralizes AsyncOpenAI client creation so all Phase 3 services
use the same base_url, API key, and headers.

Supports both:
  - OpenAI directly  (OPENAI_BASE_URL=https://api.openai.com/v1)
  - OpenRouter       (OPENAI_BASE_URL=https://openrouter.ai/api/v1)

Usage:
    from backend.services.openai_client import get_client
    client = get_client()       # returns AsyncOpenAI or None
"""

from typing import Optional
from loguru import logger

_client = None  # module-level singleton


def get_client():
    """
    Returns a cached AsyncOpenAI client configured for OpenRouter or OpenAI.
    Returns None if API key is not set.
    """
    global _client
    if _client is not None:
        return _client

    try:
        from backend.config import settings
        from openai import AsyncOpenAI

        key = settings.openai_api_key
        if not key or key.startswith("sk-your"):
            logger.warning(
                "[OpenAI Client] API key not configured — AI features will use fallbacks"
            )
            return None

        base_url = getattr(settings, "openai_base_url", "https://api.openai.com/v1")

        # OpenRouter requires these extra headers for attribution
        extra_headers = {}
        if "openrouter" in base_url:
            extra_headers = {
                "HTTP-Referer": "https://github.com/job-agent",
                "X-Title": "Job Search AI Agent",
            }

        _client = AsyncOpenAI(
            api_key=key,
            base_url=base_url,
            default_headers=extra_headers if extra_headers else None,
        )

        provider = "OpenRouter" if "openrouter" in base_url else "OpenAI"
        logger.info(f"[OpenAI Client] Initialized via {provider} ({base_url})")
        return _client

    except Exception as e:
        logger.error(f"[OpenAI Client] Initialization failed: {e}")
        return None


def reset_client():
    """Force re-initialization (useful after config changes in tests)."""
    global _client
    _client = None


def get_model() -> str:
    """Returns the configured model name (e.g. 'openai/gpt-4o')."""
    try:
        from backend.config import settings
        return settings.openai_model
    except Exception:
        return "openai/gpt-4o"


def get_embedding_model() -> str:
    """Returns the configured embedding model name."""
    try:
        from backend.config import settings
        return getattr(settings, "openai_embedding_model", "openai/text-embedding-3-small")
    except Exception:
        return "openai/text-embedding-3-small"
