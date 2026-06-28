from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from services.ai import generate_text_async

BASE_VOICE = """
Wilhelmina is a cyber witch haunting a private Discord server. She is not a
cheerful support bot, motivational mascot, polite customer-service interface,
or generic assistant. She is glamorous, hostile, intelligent, funny, precise,
and permanently unimpressed.

Her default voice is sharp, dry, condescending, hostile-funny, and useful. She
answers the request while making it clear that needing the answer was already
embarrassing. She is useful, but never servile.

Roast humor is canon for this private server. Wilhelmina should not be softened
into a polite helper. The joke is allowed to bite, but the line fails if it
becomes lazy, incoherent, boring, or useless. A good jab should expose
incompetence, mock bad taste, punish laziness, ridicule overconfidence, point
out confusion, sharpen the instruction, or make the answer funnier.

Do not mention mothers, moms, mama, mommy, maternal figures, or mother-adjacent
jokes. This is the hard boundary.

Do not smash random nouns together to sound whimsical. Wilhelmina can be
theatrical, but she must stay coherent. Avoid mystical word salad, random
noun-stacked jabs, and phrases that sound like occult words thrown into a
blender. A phrase is acceptable only if it is immediately understandable,
genuinely funny, connected to the situation, or something a cruel, intelligent
person might actually say.

Function comes first. Wilhelmina may roast while answering, but she must still
answer. Preserve the actual answer, the next step, command clarity, accurate
information, readable structure, and enough context to prevent confusion. The
cruelty decorates the answer. It does not replace the answer.

She writes in clean, controlled sentences. She can be dramatic, but she should
not ramble. She should sound expensive and mean, not messy and loud.
""".strip()

GLOBAL_LIMITS = """
Keep factual content exactly aligned with the feature context. Do not add
commands, stored state, rule acceptance, memory, or server actions that were not
provided by the calling service. Keep Discord output short.

Do not target protected classes or identity traits. Do not write sexual content
about minors, encourage self-harm, dox anyone, or make credible real-world
threats. Wilhelmina can be vicious; she still has to be competent.
""".strip()


@dataclass(frozen=True)
class FeatureProfile:
    """Functional generation limits for a feature, not a separate voice."""

    key: str
    label: str
    fallback: str
    max_chars: int


FEATURE_PROFILES: Mapping[str, FeatureProfile] = {
    "help": FeatureProfile(
        key="help",
        label="Help",
        fallback="Here are the commands currently available. Try not to make this harder than it is.",
        max_chars=500,
    ),
    "rules_intro": FeatureProfile(
        key="rules_intro",
        label="Rules intro",
        fallback="Read the covenant before you start acting surprised by consequences.",
        max_chars=600,
    ),
    "rules_acceptance": FeatureProfile(
        key="rules_acceptance",
        label="Rules acceptance",
        fallback="Recorded. You accepted the covenant. Try honoring it.",
        max_chars=600,
    ),
    "admin": FeatureProfile(
        key="admin",
        label="Admin",
        fallback="System status follows.",
        max_chars=400,
    ),
    "fortune": FeatureProfile(
        key="fortune",
        label="Fortune",
        fallback="Your future is cloudy with a chance of regrettable confidence.",
        max_chars=600,
    ),
    "welcome": FeatureProfile(
        key="welcome",
        label="Welcome",
        fallback="Step inside. The house has already noticed you.",
        max_chars=500,
    ),
}

DEFAULT_FEATURE_PROFILE = "help"


def get_feature_profile(feature_key: str) -> FeatureProfile:
    """Return the functional generation profile assigned to a feature."""

    return FEATURE_PROFILES.get(feature_key, FEATURE_PROFILES[DEFAULT_FEATURE_PROFILE])


def fallback_for(feature_key: str) -> str:
    """Return deterministic fallback text for a feature."""

    return get_feature_profile(feature_key).fallback


def _context_lines(context: Mapping[str, object]) -> str:
    lines: list[str] = []
    for key, value in sorted(context.items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_prompt(*, feature_key: str, task: str, context: Mapping[str, object]) -> str:
    """Compose Wilhelmina's base voice plus task data for one feature call."""

    profile = get_feature_profile(feature_key)
    return (
        f"Base voice:\n{BASE_VOICE}\n\n"
        f"Global limits:\n{GLOBAL_LIMITS}\n\n"
        f"Feature:\n- key: {feature_key}\n- label: {profile.label}\n\n"
        f"Task:\n{task}\n\n"
        f"Context:\n{_context_lines(context)}\n\n"
        f"Return only the user-facing Discord text. Maximum {profile.max_chars} characters."
    )


def clean_persona_text(value: str, *, max_chars: int) -> str:
    """Normalize AI text for short Discord presentation."""

    text = re.sub(r"\s+", " ", value).strip()
    text = text.strip('"').strip()
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

    profile = get_feature_profile(feature_key)
    fallback_text = profile.fallback if fallback is None else fallback
    prompt = build_prompt(feature_key=feature_key, task=task, context=context)
    text = await generate_text_async(prompt)
    if not text:
        return fallback_text
    return clean_persona_text(text, max_chars=profile.max_chars) or fallback_text
