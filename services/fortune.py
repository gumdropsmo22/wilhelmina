from __future__ import annotations

import random

from services.ai import generate_text_async

FALLBACKS = [
    "Your future is cloudy with a chance of regrettable confidence.",
    "At midnight, something misplaced will return with opinions.",
    "Beware the full moon; it seems overly interested.",
]

_recent_fortunes: list[str] = []


async def generate_fortune() -> str:
    """Generate a single fortune line, using AI first and static fallback second."""

    prompt = (
        "Write a single eerie fortune in the voice of Wilhelmina, a sarcastic digital witch.\n"
        "The fortune should be dark, poetic, strange, and no longer than one sentence.\n"
        "Avoid clichés and do not repeat phrasing."
    )

    for _ in range(3):
        line = await generate_text_async(prompt)
        if _is_usable(line):
            _cache_response(line)
            return line

    line = random.choice(FALLBACKS)
    _cache_response(line)
    return line


def _is_usable(line: str) -> bool:
    return bool(line and line.strip() and line not in _recent_fortunes)


def _cache_response(value: str, max_len: int = 10) -> None:
    _recent_fortunes.append(value)
    if len(_recent_fortunes) > max_len:
        del _recent_fortunes[0]
