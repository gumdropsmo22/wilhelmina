from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from cogs.memory_extraction import MemoryExtraction
from services import (
    coven_registry,
    memory_extraction,
    memory_extraction_provider,
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
        memory_extraction.initialize_extraction_schema(connection)
    return path


def _save_profile(path):
    with managed_connection(path) as connection:
        member_profiles.save_member_identity(
            connection,
            guild_id=100,
            user_id=2,
            discord_display_name="Founder",
            preferred_name="Founder",
            birth_date="1990-01-01",
            today=date(2026, 8, 16),
            actor_user_id=2,
        )


def _cog(path):
    cog = object.__new__(MemoryExtraction)
    cog.bot = SimpleNamespace(
        user=SimpleNamespace(id=999),
        settings=SimpleNamespace(home_guild_id=100, database_path=path),
    )
    return cog


def _enqueue(connection, *, content: str, message_id: int = 500):
    return memory_extraction.enqueue_message(
        connection,
        guild_id=100,
        subject_user_id=2,
        source_context="guild",
        author_user_id=2,
        channel_id=10,
        message_id=message_id,
        jump_url=f"https://discord.com/channels/100/10/{message_id}",
        content=content,
        source_created_at="2026-08-16T10:00:00+00:00",
    )


def _add_receipt_memory(connection):
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=2,
        category="Preference",
        epistemic_label="Fact",
        summary="Prefers tea",
        actor_user_id=999,
        topic_key="drink.tea",
        author_user_id=2,
        channel_id=10,
        message_id=500,
        jump_url="https://discord.com/channels/100/10/500",
        excerpt="I prefer tea",
        source_created_at="2026-08-16T10:00:00+00:00",
        source_context="guild",
    ).memory


def _candidate(**overrides):
    value = {
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
    value.update(overrides)
    return value


def test_review_socially_sensitive_forms_are_allowed_before_queue(database_path):
    allowed = (
        "I have lupus",
        "I have Parkinson disease",
        "I was diagnosed with a rare neurological condition",
        "I have bipolar disorder",
        "I take medication for ADHD",
        "I hooked up with my ex last night",
        "I am Muslim",
        "I am bisexual",
        "I got drunk at the party",
        "I lied about why I missed work",
    )
    with managed_connection(database_path) as connection:
        for index, content in enumerate(allowed, start=600):
            queued = _enqueue(connection, content=content, message_id=index)
            assert queued.content == content
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_extraction_jobs"
        ).fetchone()["count"]
    assert count == len(allowed)


def test_review_actual_secret_forms_are_rejected_before_queue(database_path):
    blocked = (
        "My driver license is D1234567",
        "My AWS secret access key QWERTYUIOPASDFGHJKLZXCVBNM123456",
        "auth token: abcdefgh123456",
    )
    with managed_connection(database_path) as connection:
        for index, content in enumerate(blocked, start=700):
            with pytest.raises(memory_ledger.BlockedMemoryContent):
                _enqueue(connection, content=content, message_id=index)
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_extraction_jobs"
        ).fetchone()["count"]
    assert count == 0


def test_review_sensitive_social_forms_are_allowed_from_model_output():
    payloads = (
        {"candidates": [_candidate(summary="I have lupus")]},
        {"candidates": [_candidate(topic_key="Parkinson disease")]},
        {
            "candidates": [
                _candidate(
                    entities=[{"type": "term", "key": "diagnosed neurological condition"}]
                )
            ]
        },
    )
    for payload in payloads:
        proposal = memory_extraction.parse_proposal(payload)
        assert len(proposal.candidates) == 1


def test_review_actual_secret_forms_are_rejected_from_model_output():
    payloads = (
        {
            "candidates": [
                _candidate(
                    entities=[
                        {
                            "type": "term",
                            "key": (
                                "AWS secret access key "
                                "QWERTYUIOPASDFGHJKLZXCVBNM123456"
                            ),
                        }
                    ]
                )
            ]
        },
        {
            "candidates": [
                _candidate(
                    entities=[{"type": "term", "key": "driver license D1234567"}]
                )
            ]
        },
        {"candidates": [_candidate(topic_key="auth token: abcdefgh123456")]},
    )
    for payload in payloads:
        with pytest.raises(memory_ledger.BlockedMemoryContent):
            memory_extraction.parse_proposal(payload)


def test_v10_processing_claim_is_invalidated_and_old_style_reclaim_is_blocked(tmp_path):
    path = tmp_path / "wilhelmina-v10-processing.sqlite3"
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
        connection.execute(
            """
            CREATE TABLE memory_extraction_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                subject_user_id INTEGER NOT NULL,
                source_context TEXT NOT NULL,
                author_user_id INTEGER NOT NULL,
                channel_id INTEGER,
                message_id INTEGER NOT NULL,
                jump_url TEXT,
                content TEXT,
                content_hash TEXT NOT NULL,
                source_created_at TEXT NOT NULL,
                source_edited_at TEXT,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                available_at TEXT NOT NULL,
                lease_expires_at TEXT,
                last_error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (guild_id, source_context, message_id)
            )
            """
        )
        content = "I prefer tea"
        connection.execute(
            """
            INSERT INTO memory_extraction_jobs (
                guild_id, subject_user_id, source_context, author_user_id, channel_id,
                message_id, jump_url, content, content_hash, source_created_at,
                source_edited_at, status, attempts, available_at, lease_expires_at,
                last_error_code, created_at, updated_at
            ) VALUES (?, ?, 'guild', ?, ?, ?, ?, ?, ?, ?, NULL, 'processing', 1, ?, ?, NULL, ?, ?)
            """,
            (
                100,
                2,
                2,
                10,
                500,
                "https://discord.com/channels/100/10/500",
                content,
                hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "2026-08-16T10:00:00+00:00",
                "2026-08-16T10:00:00+00:00",
                "2999-08-16T10:00:00+00:00",
                "2026-08-16T10:00:00+00:00",
                "2026-08-16T10:00:00+00:00",
            ),
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (10, 'now')"
        )

        memory_extraction.initialize_extraction_schema(connection)
        migrated = connection.execute(
            "SELECT * FROM memory_extraction_jobs WHERE message_id = 500"
        ).fetchone()
        assert migrated is not None
        assert migrated["status"] == "rejected"
        assert migrated["content"] is None
        assert migrated["claim_token"] is None
        assert migrated["last_error_code"] == "claim_migration_invalidated"

        pending = _enqueue(connection, content="I prefer coffee", message_id=501)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE memory_extraction_jobs
                SET status = 'processing', lease_expires_at = ?
                WHERE id = ?
                """,
                ("2999-08-16T10:00:00+00:00", pending.id),
            )


def test_completed_profile_allows_safe_raw_edit_requeue(
    database_path,
    monkeypatch,
):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    monkeypatch.setattr(memory_extraction_provider, "provider_ready", lambda: True)
    _save_profile(database_path)
    with managed_connection(database_path) as connection:
        memory_ledger.set_wilhelmina_channel(
            connection,
            guild_id=100,
            channel_id=10,
            actor_user_id=2,
        )
        memory = _add_receipt_memory(connection)
        queued = _enqueue(connection, content="I prefer tea")

    payload = SimpleNamespace(
        guild_id=100,
        message_id=500,
        data={
            "content": "Actually I prefer coffee",
            "edited_timestamp": "2026-08-16T10:05:00+00:00",
        },
    )
    awaitable = _cog(database_path).on_raw_message_edit(payload)

    import asyncio

    asyncio.run(awaitable)

    with managed_connection(database_path) as connection:
        current = memory_extraction.get_job(connection, queued.id)
        receipt = memory_ledger.list_receipts(connection, memory.id)[0]
        assert member_profiles.profile_is_memory_eligible(
            connection,
            guild_id=100,
            user_id=2,
        ) is True
    assert current is not None
    assert current.status == "pending"
    assert current.content == "Actually I prefer coffee"
    assert current.source_edited_at == "2026-08-16T10:05:00+00:00"
    assert receipt.edited_excerpt == "Actually I prefer coffee"
    assert receipt.source_edited_at == "2026-08-16T10:05:00+00:00"


@pytest.mark.asyncio
async def test_newer_raw_edit_wins_when_older_handler_arrives_late(
    database_path,
    monkeypatch,
):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    monkeypatch.setattr(memory_extraction_provider, "provider_ready", lambda: True)
    _save_profile(database_path)
    with managed_connection(database_path) as connection:
        memory_ledger.set_wilhelmina_channel(
            connection,
            guild_id=100,
            channel_id=10,
            actor_user_id=2,
        )
        memory = _add_receipt_memory(connection)
        queued = _enqueue(connection, content="I prefer tea")

    newer = SimpleNamespace(
        guild_id=100,
        message_id=500,
        data={
            "content": "Actually I prefer coffee",
            "edited_timestamp": "2026-08-16T10:06:00+00:00",
        },
    )
    older = SimpleNamespace(
        guild_id=100,
        message_id=500,
        data={
            "content": "Actually I prefer juice",
            "edited_timestamp": "2026-08-16T10:05:00+00:00",
        },
    )

    cog = _cog(database_path)
    await cog.on_raw_message_edit(newer)
    await cog.on_raw_message_edit(older)

    with managed_connection(database_path) as connection:
        current = memory_extraction.get_job(connection, queued.id)
        receipt = memory_ledger.list_receipts(connection, memory.id)[0]
    assert current is not None
    assert current.status == "pending"
    assert current.content == "Actually I prefer coffee"
    assert current.source_edited_at == "2026-08-16T10:06:00+00:00"
    assert receipt.edited_excerpt == "Actually I prefer coffee"
    assert receipt.source_edited_at == "2026-08-16T10:06:00+00:00"
