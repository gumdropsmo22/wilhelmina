from __future__ import annotations

import random

from services.ai import generate_text_async

INTENT_POOL = (["yes"] * 10) + (["no"] * 10) + (["maybe"] * 5) + (["ask-again"] * 5)

FALLBACKS: dict[str, list[str]] = {
    "yes": [
        "The cauldron bubbles yes.",
        "Stars align, yes.",
        "Without a doubt, dear.",
    ],
    "no": [
        "No. Even the bones made a face.",
        "The void laughs and declines.",
        "Absolutely not.",
    ],
    "maybe": [
        "Fate is fickle.",
        "Omens are mixed.",
    ],
    "ask-again": [
        "Ask after midnight.",
        "Rephrase it and try again.",
    ],
}

_recent_answers: list[str] = []


def choose_intent() -> str:
    """Choose a weighted 8-ball intent."""

    return random.choice(INTENT_POOL)


async def generate_answer(intent: str) -> str:
    """Generate one Magic 8-Ball answer, using AI first and static fallback second."""

    intent = intent.lower()
    prompt = (
        "You are Wilhelmina, a mystical digital witch.\n"
        f"Respond to a Magic 8-Ball question with one sentence implying: {intent.upper()}.\n"
        "Keep it eerie, sarcastic, or dramatic. Do not mention categories."
    )

    for _ in range(3):
        line = await generate_text_async(prompt)
        if _is_usable(line):
            _cache_response(line)
            return line

    line = random.choice(FALLBACKS.get(intent, ["The signal refuses to answer."]))
    _cache_response(line)
    return line


def format_question(question: str) -> str:
    """Return a quoted question display string."""

    question = question.strip()
    if '"' in question and "'" not in question:
        return f"'{question}'"

    return f'"{question}"'


def _is_usable(line: str) -> bool:
    return bool(line and line.strip() and line not in _recent_answers)


def _cache_response(value: str, max_len: int = 10) -> None:
    _recent_answers.append(value)
    if len(_recent_answers) > max_len:
        del _recent_answers[0]
