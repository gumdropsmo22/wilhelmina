from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from cogs.memory_extraction import MemoryExtraction, _mentioned_member_ids
from services import coven_registry, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection


@pytest.fixture()
def database_path(tmp_path):
    path = tmp_path / "wilhelmina.sqlite3"
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
        memory_ledger.initialize_memory_schema(connection)
    return path


def _grant_consent(path):
    with managed_connection(path) as connection:
        member_profiles.save_member_identity(
            connection,
            guild_id=100,
            user_id=2,
            discord_display_name="Founder",
            preferred_name="Founder",
            birth_date="1990-01-01",
            today=date(2026, 8, 13),
            adult_memory_consent=True,
            actor_user_id=2,
        )


def _cog(path):
    cog = object.__new__(MemoryExtraction)
    cog.bot = SimpleNamespace(
        user=SimpleNamespace(id=999),
        settings=SimpleNamespace(home_guild_id=100, database_path=path),
    )
    return cog


def _message(*, guild_id=100, channel_id=10, content="hello", mentions=(), author_bot=False):
    guild = None if guild_id is None else SimpleNamespace(id=guild_id)
    return SimpleNamespace(
        id=500,
        guild=guild,
        channel=SimpleNamespace(id=channel_id),
        author=SimpleNamespace(id=2, bot=author_bot),
        webhook_id=None,
        content=content,
        mentions=list(mentions),
        reference=None,
        jump_url="https://discord.com/channels/100/10/500",
        created_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
        edited_at=None,
    )


@pytest.mark.asyncio
async def test_runtime_off_blocks_before_collection(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "off")
    result = await _cog(database_path)._eligibility(_message())
    assert result.eligible is False
    assert result.reason == "runtime_off"


@pytest.mark.asyncio
async def test_current_consent_is_required(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    result = await _cog(database_path)._eligibility(
        _message(mentions=(SimpleNamespace(id=999),))
    )
    assert result.eligible is False
    assert result.reason == "consent_missing"


@pytest.mark.asyncio
async def test_dm_with_current_consent_is_eligible(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    result = await _cog(database_path)._eligibility(_message(guild_id=None))
    assert result.eligible is True
    assert result.guild_id == 100
    assert result.source_context == "dm"


@pytest.mark.asyncio
async def test_designated_channel_is_explicit_wilhelmina_interaction(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    with managed_connection(database_path) as connection:
        memory_ledger.set_wilhelmina_channel(
            connection,
            guild_id=100,
            channel_id=10,
            actor_user_id=2,
        )
    result = await _cog(database_path)._eligibility(_message(channel_id=10))
    assert result.eligible is True
    assert result.source_context == "guild"


@pytest.mark.asyncio
async def test_mention_is_eligible_outside_designated_channel(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    result = await _cog(database_path)._eligibility(
        _message(channel_id=20, mentions=(SimpleNamespace(id=999),))
    )
    assert result.eligible is True


@pytest.mark.asyncio
async def test_unaddressed_guild_message_is_not_ambient_collection(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "ambient")
    monkeypatch.setenv("ENABLE_AMBIENT_MEMORY", "true")
    monkeypatch.setenv("AMBIENT_MEMORY_APPROVAL_REFERENCE", "future-reference")
    _grant_consent(database_path)
    result = await _cog(database_path)._eligibility(_message(channel_id=20))
    assert result.eligible is False
    assert result.reason == "not_interaction"


@pytest.mark.asyncio
async def test_persistent_pause_blocks_collection(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    with managed_connection(database_path) as connection:
        memory_ledger.set_collection_enabled(
            connection,
            guild_id=100,
            enabled=False,
            actor_user_id=2,
        )
    result = await _cog(database_path)._eligibility(
        _message(mentions=(SimpleNamespace(id=999),))
    )
    assert result.eligible is False
    assert result.reason == "persistent_pause"


@pytest.mark.asyncio
async def test_bot_and_wrong_guild_are_rejected(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    bot_message = await _cog(database_path)._eligibility(_message(author_bot=True))
    wrong_guild = await _cog(database_path)._eligibility(
        _message(guild_id=101, mentions=(SimpleNamespace(id=999),))
    )
    assert bot_message.reason == "non_human"
    assert wrong_guild.reason == "wrong_guild"


def test_mentioned_member_ids_are_deduped_and_exclude_wilhelmina():
    assert _mentioned_member_ids(
        "<@77> hi <@999> and <@!77> plus <@88>",
        bot_user_id=999,
    ) == (77, 88)
