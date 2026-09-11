from __future__ import annotations

from services.persona import fallback_for, render_persona_text

WELCOME_TASK = (
    "Write one short Wilhelmina welcome line for a human who just joined the configured "
    "private Discord server. Be sharp, hostile-funny, and concise. Do not invent facts about "
    "the member, do not mention commands or onboarding steps that are not provided here, and "
    "do not turn the line into customer-service copy."
)


async def build_welcome_text(*, display_name: str) -> str:
    """Return one short Wilhelmina-styled join greeting with a deterministic fallback."""

    fallback = fallback_for("welcome")
    return await render_persona_text(
        feature_key="welcome",
        task=WELCOME_TASK,
        context={"member_display_name": display_name},
        fallback=fallback,
    )


def format_welcome_message(*, member_mention: str, text: str) -> str:
    """Attach the joining member mention without letting generated text choose the target."""

    body = (text or fallback_for("welcome")).strip() or fallback_for("welcome")
    return f"{member_mention} — {body}"
