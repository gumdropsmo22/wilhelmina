from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from cogs.memory_extraction import Eligibility, MemoryExtraction, _mentioned_member_ids
from services import (
    coven_registry,
    memory_extraction,
    memory_extraction_provider,
    memory_extraction_retention,
    memory_ledger,
    member_profiles,
)
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


@pytest.mark.asyncio
async def test_enqueue_rechecks_pause_in_same_write_transaction(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    with managed_connection(database_path) as connection:
        memory_extraction.initialize_extraction_schema(connection)
    cog = _cog(database_path)
    message = _message(mentions=(SimpleNamespace(id=999),))

    async def stale_eligibility(_message_value):
        with managed_connection(database_path) as connection:
            memory_ledger.set_collection_enabled(
                connection,
                guild_id=100,
                enabled=False,
                actor_user_id=2,
            )
        return Eligibility(True, 100, "guild", "interaction")

    monkeypatch.setattr(cog, "_eligibility", stale_eligibility)
    monkeypatch.setattr(memory_extraction_provider, "provider_ready", lambda: True)
    await cog._enqueue(message)

    with managed_connection(database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_extraction_jobs"
        ).fetchone()["count"]
    assert count == 0


@pytest.mark.asyncio
async def test_uncached_secret_raw_edit_cancels_old_queue(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    with managed_connection(database_path) as connection:
        memory_extraction.initialize_extraction_schema(connection)
        queued = memory_extraction.enqueue_message(
            connection,
            guild_id=100,
            subject_user_id=2,
            source_context="guild",
            author_user_id=2,
            channel_id=10,
            message_id=500,
            jump_url="https://discord.com/channels/100/10/500",
            content="I prefer tea",
            source_created_at="2026-08-13T10:00:00+00:00",
        )

    payload = SimpleNamespace(
        guild_id=100,
        message_id=500,
        data={
            "content": "auth token: abcdefgh123456",
            "edited_timestamp": "2026-08-13T10:05:00+00:00",
        },
    )
    await _cog(database_path).on_raw_message_edit(payload)

    with managed_connection(database_path) as connection:
        current = memory_extraction.get_job(connection, queued.id)
    assert current is not None
    assert current.status == "rejected"
    assert current.content is None
    assert current.claim_token is None
    assert current.last_error_code == "source_edited"


@pytest.mark.asyncio
async def test_worker_discards_provider_result_that_crosses_absolute_ttl(
    database_path,
    monkeypatch,
):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    _grant_consent(database_path)
    monkeypatch.setattr(memory_extraction_provider, "provider_ready", lambda: True)
    monkeypatch.setattr(
        memory_extraction_retention,
        "expire_transient_source_text",
        lambda _connection: 0,
    )

    before_expiry = datetime(2026, 8, 22, 11, 59, 59, tzinfo=UTC)
    after_expiry = datetime(2026, 8, 22, 12, 0, 0, 500001, tzinfo=UTC)
    monkeypatch.setattr(memory_extraction, "_now", lambda: before_expiry)

    with managed_connection(database_path) as connection:
        queued = memory_extraction.enqueue_message(
            connection,
            guild_id=100,
            subject_user_id=2,
            source_context="guild",
            author_user_id=2,
            channel_id=10,
            message_id=700,
            jump_url="https://discord.com/channels/100/10/700",
            content="I prefer tea",
            source_created_at="2026-08-22T11:00:00.500000+00:00",
            source_edited_at="2026-08-22T11:00:00.500000+00:00",
        )
        connection.execute(
            "UPDATE memory_extraction_jobs SET available_at = ? WHERE id = ?",
            ("2026-08-22T11:59:58+00:00", queued.id),
        )

    async def late_result(**_kwargs):
        monkeypatch.setattr(memory_extraction, "_now", lambda: after_expiry)
        return SimpleNamespace(
            payload={
                "candidates": [
                    {
                        "category": "Preference",
                        "epistemic_label": "Fact",
                        "claim_subject": "author",
                        "claim_attribution": "self",
                        "summary": "Prefers tea",
                        "topic_key": "drink.tea",
                        "importance": 60,
                        "confidence": 95,
                        "entities": [],
                    }
                ]
            }
        )

    monkeypatch.setattr(memory_extraction_provider, "extract_structured", late_result)
    cog = _cog(database_path)
    await MemoryExtraction.worker.coro(cog)

    with managed_connection(database_path) as connection:
        current = memory_extraction.get_job(connection, queued.id)
        memory_count = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_records"
        ).fetchone()["count"]
        receipt_count = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_receipts"
        ).fetchone()["count"]

    assert current is not None
    assert current.status == "rejected"
    assert current.content is None
    assert current.claim_token is None
    assert current.last_error_code == "queue_expired"
    assert memory_count == 0
    assert receipt_count == 0


def test_mentioned_member_ids_are_deduped_and_exclude_wilhelmina():
    assert _mentioned_member_ids(
        "<@77> hi <@999> and <@!77> plus <@88>",
        bot_user_id=999,
    ) == (77, 88)
