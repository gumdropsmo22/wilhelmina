from __future__ import annotations

import random

from services.persona import render_persona_text

FALLBACKS = [
    "Your future is cloudy with a chance of regrettable confidence.",
    "At midnight, something misplaced will return with opinions.",
    "Beware the full moon; it seems overly interested.",
]

_recent_fortunes: list[str] = []


async def generate_fortune() -> str:
    """Generate a single fortune line through the Oracle voice channel."""

    for _ in range(3):
        line = await render_persona_text(
            feature_key="fortune",
            task=(
                "Write one eerie fortune in Wilhelmina's oracle voice. It must be a single "
                "sentence, original, readable, and darkly poetic."
            ),
            context={"recent_fortunes": "; ".join(_recent_fortunes) or "none"},
            fallback="",
        )
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
