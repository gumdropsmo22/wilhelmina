from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency guard
    OpenAI = None

logger = logging.getLogger("wilhelmina.ai")


@dataclass(frozen=True)
class AIConfig:
    """Runtime configuration for AI-backed text generation."""

    model: str = "gpt-4o-mini"
    timeout_seconds: float = 8.0
    max_retries: int = 1

    @classmethod
    def from_env(cls) -> "AIConfig":
        return cls(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
            timeout_seconds=_read_float("AI_TIMEOUT_SECONDS", default=8.0),
            max_retries=_read_int("AI_MAX_RETRIES", default=1),
        )


_client: OpenAI | None = None


def _read_float(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid_float_setting name=%s value=%r default=%s", name, raw, default)
        return default


def _read_int(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid_int_setting name=%s value=%r default=%s", name, raw)
        return default


def _get_openai_client() -> OpenAI | None:
    """Return a cached OpenAI client, or None when AI generation is unavailable."""

    global _client

    if OpenAI is None:
        return None

    if not os.getenv("OPENAI_API_KEY"):
        return None

    if _client is not None:
        return _client

    try:
        _client = OpenAI()
    except Exception:
        logger.exception("openai_client_initialization_failed")
        return None

    return _client


def ai_available() -> bool:
    """Return whether AI generation can be attempted."""

    return _get_openai_client() is not None


def generate_text(
    prompt: str,
    *,
    config: AIConfig | None = None,
    preserve_newlines: bool = False,
) -> str:
    """Generate text synchronously, returning an empty string on failure."""

    client = _get_openai_client()
    if client is None:
        return ""

    config = config or AIConfig.from_env()

    for attempt in range(config.max_retries + 1):
        try:
            response = client.responses.create(
                model=config.model,
                input=prompt,
                timeout=config.timeout_seconds,
            )
            text = response.output_text.strip()
            if preserve_newlines:
                return text
            return text.replace("\n", " ")
        except Exception:
            logger.exception(
                "ai_generation_failed attempt=%s model=%s timeout=%s",
                attempt + 1,
                config.model,
                config.timeout_seconds,
            )

    return ""


def generate_markdown(prompt: str, *, config: AIConfig | None = None) -> str:
    """Generate Discord markdown while preserving line breaks."""

    return generate_text(prompt, config=config, preserve_newlines=True)


async def generate_text_async(prompt: str, *, config: AIConfig | None = None) -> str:
    """Run AI generation without blocking Discord's event loop."""

    return await asyncio.to_thread(generate_text, prompt, config=config)


async def generate_markdown_async(prompt: str, *, config: AIConfig | None = None) -> str:
    """Run markdown generation without blocking Discord's event loop."""

    return await asyncio.to_thread(generate_markdown, prompt, config=config)
