from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from cogs.chat import Chat
from services import chat_response, coven_registry, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection

TODAY = date(2026, 8, 24)


def _setup(path) -> None:
    initialize_database(path)
    with managed_connection(path) as connection:
        coven_registry.bootstrap_registry(
            connection,
            guild_id=100,
            wilhelmina_user_id=999,
            founder_user_id=2,
            founder_name="Founder",
            actor_user_id=2,
        )
        member_profiles.save_member_identity(
            connection,
            guild_id=100,
            user_id=2,
            discord_display_name="Founder",
            preferred_name="Mina",
            birth_date="1990-10-31",
            today=TODAY,
            actor_user_id=2,
        )
        memory_ledger.set_wilhelmina_channel(
            connection,
            guild_id=100,
            channel_id=10,
            actor_user_id=2,
        )


def _bot(path):
    return SimpleNamespace(
        user=SimpleNamespace(id=999),
        settings=SimpleNamespace(home_guild_id=100, database_path=path),
        command_prefix="!",
    )


def _message(*, channel_id: int = 10, content: str = "hello"):
    return SimpleNamespace(
        id=500,
        author=SimpleNamespace(id=2, bot=False),
        webhook_id=None,
        content=content,
        guild=SimpleNamespace(id=100),
        channel=SimpleNamespace(id=channel_id),
        mentions=[],
        reference=None,
        reply=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_chat_cog_prepares_context_generates_and_replies(
    tmp_path,
    caplog,
    monkeypatch,
):
    path = tmp_path / "chat.sqlite3"
    _setup(path)
    cog = Chat(_bot(path))
    message = _message()

    async def fake_generate(**kwargs):
        assert kwargs["current_message"] == "hello"
        return chat_response.ChatReply(
            text="Darling, hello.",
            provider_used=True,
            model="chat-model",
            request_id="req_1",
        )

    monkeypatch.setattr(chat_response, "generate_chat_reply_async", fake_generate)

    with caplog.at_level("INFO", logger="wilhelmina.chat.events"):
        await cog.on_message(message)

    assert "chat_context_prepared" in caplog.text
    assert "surface=designated_channel" in caplog.text
    assert "chat_reply_sent" in caplog.text
    message.reply.assert_awaited_once()
    args, kwargs = message.reply.await_args
    assert args == ("Darling, hello.",)
    assert kwargs["mention_author"] is False
    assert kwargs["fail_if_not_exists"] is False
    allowed_mentions = kwargs["allowed_mentions"]
    assert isinstance(allowed_mentions, discord.AllowedMentions)
    assert allowed_mentions.everyone is False
    assert allowed_mentions.users is False
    assert allowed_mentions.roles is False


@pytest.mark.asyncio
async def test_chat_cog_ignores_unaddressed_non_designated_guild_message(
    tmp_path,
    caplog,
    monkeypatch,
):
    path = tmp_path / "chat.sqlite3"
    _setup(path)
    cog = Chat(_bot(path))
    message = _message(channel_id=20)
    called = False

    async def should_not_generate(**kwargs):
        nonlocal called
        called = True
        return chat_response.ChatReply(text="no", provider_used=False)

    monkeypatch.setattr(chat_response, "generate_chat_reply_async", should_not_generate)

    with caplog.at_level("INFO", logger="wilhelmina.chat.events"):
        await cog.on_message(message)

    assert called is False
    assert message.reply.await_count == 0
    assert "chat_context_prepared" not in caplog.text
