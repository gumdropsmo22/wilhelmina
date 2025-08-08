import random
import logging
from typing import List

from openai import OpenAI


_client = OpenAI()


# Cryptic lore lines for numbers (used in /roll)
def number_lore(n: int) -> str:
    """Return a cryptic, poetic line keyed to the number n, in Wilhelmina's tone."""
    # Special-case notable numbers with custom lore
    special_cases = {
        1: "The loneliest number—divisible by none.",
        3: "Third time's the harm; chaos thrives.",
        5: "Five points on the star, each hungry.",
        7: "Lucky number? Not for you.",
        12: "A dozen devils dance unseen.",
        13: "The stair that isn't there. Step anyway.",
        42: "The answer to everything and nothing.",
        69: "Even demons blush at that position.",
        666: "The mark of the beast—fond of you, isn't it?",
        777: "Angelic jackpot? The payout is pain.",
        100: "A perfect hundred—too neat to trust.",
        1000: "A thousand souls cry out at once.",
    }
    if n in special_cases:
        return special_cases[n]
    # Determine number properties
    is_prime = False
    if n > 1:
        is_prime = all(n % i != 0 for i in range(2, int(n**0.5) + 1))
    if is_prime:
        return "Prime and indivisible—alone in the void."
    if n % 2 == 0:  # even (non-prime composite evens)
        return "Even and dull—symmetry bores me."
    else:  # odd (non-prime composite odds)
        return "Odd and unruly—just my style."


def generate_openai_response(prompt: str) -> str:
    """Send prompt to OpenAI and return a trimmed response, or empty string on failure."""
    try:
        resp = _client.responses.create(model="gpt-4o-mini", input=prompt)
        text = resp.output_text.strip()
        return text.replace("\n", " ")
    except Exception as exc:  # pragma: no cover - best effort logging
        logging.exception("OpenAI generation failed: %s", exc)
        return ""


def _cache_response(cache: List[str], value: str, max_len: int = 10) -> None:
    cache.append(value)
    if len(cache) > max_len:
        del cache[0]


_eight_ball_cache: List[str] = []


def generate_eight_ball(intent: str) -> str:
    """Generate one Magic 8-Ball line via OpenAI, falling back to static lines on failure."""
    intent = intent.lower()
    prompt = (
        "You are Wilhelmina, a mystical digital witch.\n"
        f"Respond to a Magic 8-Ball question with a one-sentence answer that implies the outcome is: {intent.upper()}.\n"
        "Keep it eerie, sarcastic, or dramatic. Never repeat previous answers."
    )
    for _ in range(3):
        line = generate_openai_response(prompt)
        if line and line not in _eight_ball_cache:
            _cache_response(_eight_ball_cache, line)
            return line
    fallbacks = {
        "yes": [
            "The cauldron bubbles yes.",
            "Stars align, yes.",
            "Without a doubt, dear.",
        ],
        "no": [
            "No. Even the bones said 'ew'.",
            "The void laughs.",
            "Absolutely not.",
        ],
        "maybe": [
            "Fate is fickle.",
            "Omens are mixed.",
        ],
        "ask-again": [
            "Ask after midnight.",
            "Bring a sacrifice and ask again.",
        ],
    }
    choice = random.choice(fallbacks.get(intent, ["The void stays silent."]))
    _cache_response(_eight_ball_cache, choice)
    return choice


_fortune_cache: List[str] = []


def generate_fortune() -> str:
    """Generate a single fortune line via OpenAI with fallback to static phrases."""
    prompt = (
        "Write a single eerie fortune in the voice of Wilhelmina, a sarcastic digital witch.\n"
        "The fortune should be dark, poetic, strange, and no longer than one sentence.\n"
        "Never reuse past phrasing. Avoid clichés."
    )
    for _ in range(3):
        line = generate_openai_response(prompt)
        if line and line not in _fortune_cache:
            _cache_response(_fortune_cache, line)
            return line
    fallbacks = [
        "Your future: cloudy with a chance of regret.",
        "At midnight, something lost returns with teeth.",
        "Beware the full moon; it likes you too much.",
    ]
    choice = random.choice(fallbacks)
    _cache_response(_fortune_cache, choice)
    return choice

