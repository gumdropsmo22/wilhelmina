from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cogs.chat import Chat
from services import chat_response, coven_registry, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection

TODAY = date(2026, 8, 28)


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


def _message():
    return SimpleNamespace(
        id=950,
        author=SimpleNamespace(id=2, bot=False),
        webhook_id=None,
        content="ordinary question",
        guild=SimpleNamespace(id=100),
        channel=SimpleNamespace(id=10),
        mentions=[],
        reference=None,
        reply=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_delete_during_discord_send_retracts_just_sent_reply_and_skips_history(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "chat.sqlite3"
    _setup(path)
    cog = Chat(_bot(path))
    message = _message()
    sent = SimpleNamespace(delete=AsyncMock())

    async def fake_generate(**kwargs):
        return chat_response.ChatReply(text="generated answer", provider_used=True)

    async def send_then_delete(*args, **kwargs):
        await cog.on_raw_message_delete(SimpleNamespace(guild_id=100, message_id=950))
        return sent

    monkeypatch.setattr(chat_response, "generate_chat_reply_async", fake_generate)
    message.reply.side_effect = send_then_delete

    await cog.on_message(message)

    message.reply.assert_awaited_once()
    sent.delete.assert_awaited_once()
    assert all(not entries for entries in cog.runtime._histories.values())
