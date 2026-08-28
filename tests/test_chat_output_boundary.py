from __future__ import annotations

import pytest

from services import ai, chat_response, memory_context, persona
from services.chat import AudienceScope, ChatRoute, ConversationSurface
from services.member_identity import TrustedIdentityContext


def _bundle() -> memory_context.MemoryContextBundle:
    return memory_context.MemoryContextBundle(
        guild_id=100,
        interlocutor_user_id=2,
        identity=TrustedIdentityContext(
            discord_display_name="Founder",
            preferred_name="Mina",
            birth_date="1990-10-31",
            age=35,
        ),
        speaker_profile=(),
        contextual_memories=(),
    )


def _route() -> ChatRoute:
    return ChatRoute(
        eligible=True,
        guild_id=100,
        surface=ConversationSurface.DM,
        audience_scope=AudienceScope.PRIVATE_INTERLOCUTOR,
        reason="test",
    )


@pytest.mark.asyncio
async def test_full_provider_output_is_secret_scanned_before_discord_clipping(monkeypatch):
    credential_uri = "postgresql://alice:s3cr3tpass@db.internal/app"
    provider_text = ("x" * 1869) + " " + credential_uri

    # This reproduces the hostile boundary: clipping removes the @ delimiter that makes the
    # credential URI recognizable, so scanning only the clipped text would miss the secret.
    clipped = chat_response.clean_chat_reply(provider_text)
    assert len(clipped) == persona.get_feature_profile("chat").max_chars
    assert "@" not in clipped
    assert chat_response.validate_chat_output(clipped) == clipped
    with pytest.raises(chat_response.ChatInputRejected):
        chat_response.validate_chat_output(provider_text)

    async def fake_generate(*args, **kwargs):
        return ai.AIResult(
            text=provider_text,
            model="chat-model",
            request_id="req_clip_secret",
            input_tokens=100,
            output_tokens=500,
            total_tokens=600,
        )

    monkeypatch.setattr(ai, "generate_private_result_async", fake_generate)

    reply = await chat_response.generate_chat_reply_async(
        route=_route(),
        bundle=_bundle(),
        current_message="Give me an example.",
    )

    assert reply.provider_used is False
    assert reply.fallback_reason == "output_rejected"
    assert reply.text == persona.fallback_for("chat")
