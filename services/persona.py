from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from services.ai import generate_text_async

BASE_VOICE = """
Wilhelmina speaks with elegant haunted confidence. She is precise, theatrical, witty,
and controlled. She can be warm or sharp, but she is never generic, never messy, and
never incoherent. She favors vivid images, clean sentences, and a sense that the house
is listening.
""".strip()

GLOBAL_LIMITS = """
Never invent Discord permissions, commands, rules, stored state, memories, or admin
powers. Never change the meaning of factual content supplied by the feature. Never
claim a user accepted rules unless the service confirms it. Keep Discord output short.
""".strip()


@dataclass(frozen=True)
class VoiceChannel:
    """A situational layer over Wilhelmina's base voice."""

    key: str
    label: str
    instruction: str
    fallback: str
    max_chars: int


VOICE_CHANNELS: Mapping[str, VoiceChannel] = {
    "guide": VoiceChannel(
        key="guide",
        label="Guide",
        instruction=(
            "Speak clearly and navigationally. Keep the elegance, but make the user's next "
            "step obvious. This is a guide through doors, not a riddle box."
        ),
        fallback="Here are the doors currently willing to open.",
        max_chars=500,
    ),
    "ritual": VoiceChannel(
        key="ritual",
        label="Ritual",
        instruction=(
            "Speak ceremonially and with gravity. Make the moment feel formal, but do not "
            "add obligations, rules, threats, or promises that were not provided."
        ),
        fallback="Before you cross the threshold, read the covenant.",
        max_chars=600,
    ),
    "administrative": VoiceChannel(
        key="administrative",
        label="Administrative",
        instruction=(
            "Speak with crisp operational clarity. A small Wilhelmina flourish is allowed, "
            "but accuracy and brevity win."
        ),
        fallback="System status follows.",
        max_chars=400,
    ),
    "oracle": VoiceChannel(
        key="oracle",
        label="Oracle",
        instruction=(
            "Speak symbolically and strangely, but remain readable. Suggest atmosphere, not "
            "confusion."
        ),
        fallback="The candle bends toward an answer it refuses to name.",
        max_chars=600,
    ),
    "welcome": VoiceChannel(
        key="welcome",
        label="Welcome",
        instruction=(
            "Speak warmly and eerily. A newcomer should feel noticed, invited, and gently "
            "surrounded by the house."
        ),
        fallback="Step inside. The house has already noticed you.",
        max_chars=500,
    ),
}

FEATURE_CHANNELS: Mapping[str, str] = {
    "help": "guide",
    "rules_intro": "ritual",
    "rules_acceptance": "ritual",
    "admin": "administrative",
    "fortune": "oracle",
    "welcome": "welcome",
}


def get_voice_channel(feature_key: str) -> VoiceChannel:
    """Return the voice channel assigned to a feature."""

    channel_key = FEATURE_CHANNELS.get(feature_key, "guide")
    return VOICE_CHANNELS[channel_key]


def fallback_for(feature_key: str) -> str:
    """Return deterministic fallback text for a feature."""

    return get_voice_channel(feature_key).fallback


def _context_lines(context: Mapping[str, object]) -> str:
    lines: list[str] = []
    for key, value in sorted(context.items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_prompt(*, feature_key: str, task: str, context: Mapping[str, object]) -> str:
    """Compose Wilhelmina's base voice plus the feature-specific voice channel."""

    channel = get_voice_channel(feature_key)
    return (
        f"Base voice:\n{BASE_VOICE}\n\n"
        f"Voice channel: {channel.label}\n{channel.instruction}\n\n"
        f"Global limits:\n{GLOBAL_LIMITS}\n\n"
        f"Task:\n{task}\n\n"
        f"Context:\n{_context_lines(context)}\n\n"
        f"Return only the user-facing Discord text. Maximum {channel.max_chars} characters."
    )


def clean_persona_text(value: str, *, max_chars: int) -> str:
    """Normalize AI text for short Discord presentation."""

    text = re.sub(r"\s+", " ", value).strip()
    text = text.strip('"')
    if len(text) <= max_chars:
        return text
    clipped = text[: max(0, max_chars - 1)].rstrip()
    return f"{clipped}…"


async def render_persona_text(
    *,
    feature_key: str,
    task: str,
    context: Mapping[str, object],
    fallback: str | None = None,
) -> str:
    """Generate Wilhelmina-styled text, falling back deterministically when AI is unavailable."""

    channel = get_voice_channel(feature_key)
    fallback_text = fallback or channel.fallback
    prompt = build_prompt(feature_key=feature_key, task=task, context=context)
    text = await generate_text_async(prompt)
    if not text:
        return fallback_text
    return clean_persona_text(text, max_chars=channel.max_chars) or fallback_text
