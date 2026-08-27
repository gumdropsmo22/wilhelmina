from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from cogs.memory_extraction import MemoryExtraction
from services import (
    coven_registry,
    memory_extraction,
    memory_ledger,
    memory_reconciliation,
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


def _enqueue(connection, *, content: str = "I prefer tea"):
    return memory_extraction.enqueue_message(
        connection,
        guild_id=100,
        subject_user_id=2,
        source_context="guild",
        author_user_id=2,
        channel_id=10,
        message_id=500,
        jump_url="https://discord.com/channels/100/10/500",
        content=content,
        source_created_at="2026-08-13T10:00:00+00:00",
    )


def _add_existing_receipt(connection):
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
        source_created_at="2026-08-13T10:00:00+00:00",
        source_context="guild",
    )


def _grant_consent(connection):
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


def test_stale_transient_queue_text_expires_fail_closed(database_path):
    with managed_connection(database_path) as connection:
        queued = _enqueue(connection)
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET created_at = '2000-01-01T00:00:00+00:00',
                updated_at = '2000-01-01T00:00:00+00:00'
            WHERE id = ?
            """,
            (queued.id,),
        )
        expired = memory_extraction.expire_stale_jobs(connection)
        current = memory_extraction.get_job(connection, queued.id)

    assert expired == 1
    assert current is not None
    assert current.status == "rejected"
    assert current.content is None
    assert current.last_error_code == "queue_expired"


def test_sensitive_edit_cancels_old_queue_and_never_persists_new_secret(database_path):
    sensitive = "Actually my API key is sk-abcdefghijklmnopqrstuvwxyz1234567890"
    with managed_connection(database_path) as connection:
        memory = _add_existing_receipt(connection).memory
        queued = _enqueue(connection)
        safe = memory_extraction.maintain_source_edit(
            connection,
            guild_id=100,
            message_id=500,
            edited_excerpt=sensitive,
            edited_at="2026-08-13T10:05:00+00:00",
        )
        current = memory_extraction.get_job(connection, queued.id)
        receipt = memory_ledger.list_receipts(connection, memory.id)[0]

    assert safe is False
    assert current is not None
    assert current.status == "rejected"
    assert current.content is None
    assert current.last_error_code == "source_edited"
    assert receipt.edited_excerpt == memory_extraction.SENSITIVE_EDIT_MARKER
    assert "sk-" not in receipt.edited_excerpt


def test_safe_edit_cancels_old_queue_even_before_provider_requeue(database_path):
    with managed_connection(database_path) as connection:
        memory = _add_existing_receipt(connection).memory
        queued = _enqueue(connection)
        safe = memory_extraction.maintain_source_edit(
            connection,
            guild_id=100,
            message_id=500,
            edited_excerpt="Actually I prefer coffee",
            edited_at="2026-08-13T10:05:00+00:00",
        )
        current = memory_extraction.get_job(connection, queued.id)
        receipt = memory_ledger.list_receipts(connection, memory.id)[0]

    assert safe is True
    assert current is not None
    assert current.status == "rejected"
    assert current.content is None
    assert receipt.original_excerpt == "I prefer tea"
    assert receipt.edited_excerpt == "Actually I prefer coffee"


def test_conflicting_ordinary_topics_are_rejected_before_any_mutation(database_path):
    proposal = memory_extraction.parse_proposal(
        {
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
                },
                {
                    "category": "Dislike",
                    "epistemic_label": "Fact",
                    "claim_subject": "author",
                    "claim_attribution": "self",
                    "summary": "Dislikes tea",
                    "topic_key": "drink.tea",
                    "importance": 60,
                    "confidence": 95,
                    "entities": [],
                },
            ]
        }
    )
    with managed_connection(database_path) as connection:
        _enqueue(connection)
        job = memory_extraction.claim_next_job(connection)
        assert job is not None
        with pytest.raises(memory_extraction.InvalidProposal):
            memory_reconciliation.apply_proposal(
                connection,
                job=job,
                proposal=proposal,
                actor_user_id=999,
            )
        memories = memory_ledger.list_profile(
            connection,
            guild_id=100,
            subject_user_id=2,
        )

    assert memories == []


def test_worker_authorization_rechecks_mutable_pause_gate(database_path, monkeypatch):
    monkeypatch.setenv("MEMORY_COLLECTION_MODE", "interaction")
    cog = object.__new__(MemoryExtraction)
    cog.bot = SimpleNamespace(
        settings=SimpleNamespace(home_guild_id=100, database_path=database_path),
        user=SimpleNamespace(id=999),
    )

    with managed_connection(database_path) as connection:
        _grant_consent(connection)
        queued = _enqueue(connection)
        assert cog._job_authorized(connection, queued) is True
        memory_ledger.set_collection_enabled(
            connection,
            guild_id=100,
            enabled=False,
            actor_user_id=2,
        )
        assert cog._job_authorized(connection, queued) is False
