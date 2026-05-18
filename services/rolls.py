from __future__ import annotations

import random

SPECIAL_NUMBER_LORE: dict[int, str] = {
    1: "The loneliest number, standing alone in the ledger.",
    3: "Third time's the harm; chaos thrives.",
    5: "Five points on the star, each watching.",
    7: "Lucky number? Suspiciously confident.",
    12: "A dozen echoes answer at once.",
    13: "The stair that isn't there. Step carefully.",
    42: "The answer to everything and nothing.",
    69: "The mirror winks. Rude but noted.",
    100: "A perfect hundred, too neat to trust.",
    666: "A dramatic number with excellent branding.",
    777: "A jackpot-shaped omen. Read the fine print.",
    1000: "A thousand signals arrive at once.",
}


def roll_die(sides: int) -> int:
    """Roll one die with the requested side count."""

    if sides < 2 or sides > 1000:
        raise ValueError("sides must be between 2 and 1000")

    return random.randint(1, sides)


def number_lore(number: int) -> str:
    """Return Wilhelmina-style number lore for a roll result."""

    if number in SPECIAL_NUMBER_LORE:
        return SPECIAL_NUMBER_LORE[number]

    if _is_prime(number):
        return "Prime and indivisible, alone in the void."

    if number % 2 == 0:
        return "Even and orderly. Symmetry is showing off again."

    return "Odd and unruly. Naturally, it has flair."


def _is_prime(number: int) -> bool:
    if number <= 1:
        return False

    return all(number % divisor != 0 for divisor in range(2, int(number**0.5) + 1))
