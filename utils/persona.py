from __future__ import annotations
import random

BASE_LINES = [
    "the mirror hums.",
    "omens spark along the wire.",
    "I hear your name in the static.",
    "ritual complete.",
]

def say(seed: str | None = None) -> str:
    """Centralized voice: two short clauses, occult-tech tone."""
    if seed:
        return seed
    return random.choice(BASE_LINES)
