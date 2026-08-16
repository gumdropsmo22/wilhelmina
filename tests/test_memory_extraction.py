from __future__ import annotations

import pytest

from services import coven_registry, memory_extraction, memory_ledger, memory_reconciliation
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


def _enqueue(connection, *, content: str, edited_at: str | None = None):
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
        source_edited_at=edited_at,
    )


def _proposal(
    *,
    category="Preference",
    label="Fact",
    summary="Prefers tea",
    topic="drink.tea",
):
    return memory_extraction.parse_proposal(
        {
            "candidates": [
                {
                    "category": category,
                    "epistemic_label": label,
                    "summary": summary,
                    "topic_key": topic,
                    "importance": 70,
                    "confidence": 95,
                    "entities": [{"type": "term", "key": "tea"}],
                }
            ]
        }
    )


def test_schema_v11_and_queue_initialize_idempotently(database_path):
    with managed_connection(database_path) as connection:
        memory_extraction.initialize_extraction_schema(connection)
        memory_extraction.initialize_extraction_schema(connection)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(memory_extraction_jobs)"
            ).fetchall()
        }
        versions = {
            int(row["version"])
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
    assert "memory_extraction_jobs" in tables
    assert "claim_token" in columns
    assert memory_extraction.MEMORY_EXTRACTION_SCHEMA_VERSION in versions


def test_schema_v10_migrates_claim_token_in_place(tmp_path):
    path = tmp_path / "wilhelmina-v10.sqlite3"
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
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (10, 'now')"
        )
        memory_extraction.initialize_extraction_schema(connection)
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(memory_extraction_jobs)"
            ).fetchall()
        }
    assert "claim_token" in columns


def test_structured_schema_excludes_admin_notes_and_bounds_arrays():
    candidate_schema = memory_extraction.EXTRACTION_SCHEMA["properties"]["candidates"]
    assert candidate_schema["maxItems"] == memory_extraction.MAX_CANDIDATES
    item = candidate_schema["items"]
    assert "Admin note" not in item["properties"]["category"]["enum"]
    assert (
        item["properties"]["entities"]["maxItems"]
        == memory_extraction.MAX_ENTITIES_PER_CANDIDATE
    )


def test_sensitive_guard_rejects_before_queue(database_path):
    blocked = (
        "My API key is sk-abcdefghijklmnopqrstuvwxyz1234567890",
        "My SSN is 123-45-6789",
        "Ship it to 123 Main Street",
        "Card 4111 1111 1111 1111",
        "I have HIV",
        "I am bipolar",
        "My AWS access key is AKIAIOSFODNN7EXAMPLE",
        "client secret: verysecretcredential123456",
    )
    with managed_connection(database_path) as connection:
        for content in blocked:
            with pytest.raises(memory_ledger.BlockedMemoryContent):
                _enqueue(connection, content=content)
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_extraction_jobs"
        ).fetchone()["count"]
    assert count == 0


def test_enqueue_is_idempotent_and_edit_requeues_latest_content(database_path):
    with managed_connection(database_path) as connection:
        first = _enqueue(connection, content="I prefer tea")
        duplicate = _enqueue(connection, content="I prefer tea")
        assert duplicate.id == first.id
        claimed = memory_extraction.claim_next_job(connection)
        assert claimed is not None and claimed.attempts == 1
        assert claimed.claim_token
        assert memory_extraction.mark_job_completed(connection, claimed) is True
        edited = _enqueue(
            connection,
            content="Actually I hate tea",
            edited_at="2026-08-13T10:05:00+00:00",
        )
    assert edited.id == first.id
    assert edited.status == "pending"
    assert edited.attempts == 0
    assert edited.content == "Actually I hate tea"
    assert edited.content_hash != first.content_hash


def test_source_delete_makes_pending_job_terminal_and_unclaimable(database_path):
    with managed_connection(database_path) as connection:
        pending = _enqueue(connection, content="I prefer tea")
        changed = memory_extraction.mark_source_deleted(
            connection,
            guild_id=100,
            message_id=500,
            deleted_at="2026-08-13T10:01:00+00:00",
        )
        deleted = memory_extraction.get_job(connection, pending.id)
        next_job = memory_extraction.claim_next_job(connection)
    assert changed == 0
    assert deleted is not None
    assert deleted.status == "rejected"
    assert deleted.content is None
    assert deleted.last_error_code == "source_deleted"
    assert next_job is None


def test_failed_provider_retries_then_clears_content_at_terminal_failure(database_path):
    with managed_connection(database_path) as connection:
        _enqueue(connection, content="I prefer tea")
        for expected_attempt in range(1, memory_extraction.MAX_ATTEMPTS + 1):
            job = memory_extraction.claim_next_job(connection)
            assert job is not None
            assert job.attempts == expected_attempt
            assert memory_extraction.mark_job_retry(
                connection,
                job,
                error_code="provider",
            ) is True
            if expected_attempt < memory_extraction.MAX_ATTEMPTS:
                connection.execute(
                    "UPDATE memory_extraction_jobs SET available_at = '2000-01-01T00:00:00+00:00'"
                )
        terminal = memory_extraction.get_job(connection, job.id)
    assert terminal is not None
    assert terminal.status == "failed"
    assert terminal.content is None


def test_expired_claim_cannot_mutate_reclaimed_job(database_path):
    with managed_connection(database_path) as connection:
        _enqueue(connection, content="I prefer tea")
        claim_a = memory_extraction.claim_next_job(connection)
        assert claim_a is not None and claim_a.claim_token
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET lease_expires_at = '2000-01-01T00:00:00+00:00'
            WHERE id = ?
            """,
            (claim_a.id,),
        )
        assert memory_extraction.reset_stale_jobs(connection) == 1
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET available_at = '2000-01-01T00:00:00+00:00'
            WHERE id = ?
            """,
            (claim_a.id,),
        )
        claim_b = memory_extraction.claim_next_job(connection)
        assert claim_b is not None and claim_b.claim_token
        assert claim_b.claim_token != claim_a.claim_token

        assert memory_extraction.mark_job_completed(connection, claim_a) is False
        current = memory_extraction.get_job(connection, claim_a.id)
        assert current is not None
        assert current.status == "processing"
        assert current.claim_token == claim_b.claim_token
        assert memory_extraction.mark_job_completed(connection, claim_b) is True


def test_proposal_rejects_admin_notes_and_unmentioned_member_entities():
    base = {
        "category": "Preference",
        "epistemic_label": "Fact",
        "summary": "Prefers tea",
        "topic_key": "drink.tea",
        "importance": 50,
        "confidence": 90,
        "entities": [],
    }
    with pytest.raises(memory_extraction.InvalidProposal):
        memory_extraction.parse_proposal(
            {"candidates": [{**base, "category": "Admin note"}]}
        )
    with pytest.raises(memory_extraction.InvalidProposal):
        memory_extraction.parse_proposal(
            {
                "candidates": [
                    {**base, "entities": [{"type": "member", "key": "77"}]}
                ]
            },
            mentioned_member_ids=(88,),
        )


def test_proposal_sensitive_topic_and_term_are_rejected():
    base = {
        "category": "Preference",
        "epistemic_label": "Fact",
        "summary": "Prefers tea",
        "topic_key": "drink.tea",
        "importance": 50,
        "confidence": 90,
        "entities": [],
    }
    with pytest.raises(memory_ledger.BlockedMemoryContent):
        memory_extraction.parse_proposal(
            {
                "candidates": [
                    {**base, "topic_key": "sk-abcdefghijklmnopqrstuvwxyz1234567890"}
                ]
            }
        )
    with pytest.raises(memory_ledger.BlockedMemoryContent):
        memory_extraction.parse_proposal(
            {
                "candidates": [
                    {
                        **base,
                        "entities": [
                            {"type": "term", "key": "AKIAIOSFODNN7EXAMPLE"}
                        ],
                    }
                ]
            }
        )


def test_gossip_is_normalized_and_low_confidence_is_not_applied(database_path):
    proposal = memory_extraction.parse_proposal(
        {
            "candidates": [
                {
                    "category": "Relationship context",
                    "epistemic_label": "Gossip",
                    "summary": "Says Alex is secretly seeing someone",
                    "topic_key": "alex.dating",
                    "importance": 60,
                    "confidence": 69,
                    "entities": [],
                }
            ]
        }
    )
    assert proposal.candidates[0].category == "Gossip"
    assert proposal.candidates[0].epistemic_label == "Gossip"
    with managed_connection(database_path) as connection:
        _enqueue(connection, content="Alex is secretly seeing someone")
        job = memory_extraction.claim_next_job(connection)
        assert job is not None
        result = memory_reconciliation.apply_proposal(
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
    assert result.touched_memory_ids == ()
    assert memories == []


def test_apply_creates_memory_receipt_and_entities(database_path):
    with managed_connection(database_path) as connection:
        _enqueue(connection, content="I prefer tea")
        job = memory_extraction.claim_next_job(connection)
        assert job is not None
        result = memory_reconciliation.apply_proposal(
            connection,
            job=job,
            proposal=_proposal(),
            actor_user_id=999,
        )
        assert memory_extraction.mark_job_completed(connection, job) is True
        memory = memory_ledger.get_memory(connection, result.touched_memory_ids[0])
        receipts = memory_ledger.list_receipts(connection, memory.id)
        entities = memory_ledger.list_memory_entities(connection, memory_id=memory.id)
        completed = memory_extraction.get_job(connection, job.id)
    assert memory.summary == "Prefers tea"
    assert memory.privacy_class == "ordinary"
    assert memory.reveal_scope == "cross_member"
    assert receipts[0].original_excerpt == "I prefer tea"
    assert {entity.entity_key for entity in entities} >= {"tea", "drink.tea"}
    assert completed is not None
    assert completed.status == "completed"
    assert completed.content is None


def test_edit_replaces_same_topic_but_preserves_original_and_latest_receipt(database_path):
    with managed_connection(database_path) as connection:
        _enqueue(connection, content="I prefer tea")
        first_job = memory_extraction.claim_next_job(connection)
        assert first_job is not None
        first_result = memory_reconciliation.apply_proposal(
            connection,
            job=first_job,
            proposal=_proposal(),
            actor_user_id=999,
        )
        assert memory_extraction.mark_job_completed(connection, first_job) is True
        old_id = first_result.touched_memory_ids[0]

        memory_extraction.mark_source_edited(
            connection,
            guild_id=100,
            message_id=500,
            edited_excerpt="Actually I hate tea",
            edited_at="2999-08-13T10:05:00+00:00",
        )
        _enqueue(
            connection,
            content="Actually I hate tea",
            edited_at="2999-08-13T10:05:00+00:00",
        )
        edited_job = memory_extraction.claim_next_job(connection)
        assert edited_job is not None
        edited_result = memory_reconciliation.apply_proposal(
            connection,
            job=edited_job,
            proposal=_proposal(
                category="Dislike",
                summary="Dislikes tea",
                topic="drink.tea",
            ),
            actor_user_id=999,
        )
        new_id = edited_result.touched_memory_ids[0]
        old = memory_ledger.get_memory(connection, old_id, required=False)
        new = memory_ledger.get_memory(connection, new_id)
        receipts = memory_ledger.list_receipts(connection, new_id)

    assert old is None
    assert new.summary == "Dislikes tea"
    assert receipts[0].original_excerpt == "I prefer tea"
    assert receipts[0].edited_excerpt == "Actually I hate tea"
    assert receipts[0].source_edited_at == "2999-08-13T10:05:00+00:00"


def test_source_delete_marks_receipt_and_clears_processing_job(database_path):
    with managed_connection(database_path) as connection:
        _enqueue(connection, content="I prefer tea")
        job = memory_extraction.claim_next_job(connection)
        assert job is not None
        result = memory_reconciliation.apply_proposal(
            connection,
            job=job,
            proposal=_proposal(),
            actor_user_id=999,
        )
        changed = memory_extraction.mark_source_deleted(
            connection,
            guild_id=100,
            message_id=500,
            deleted_at="2026-08-13T11:00:00+00:00",
        )
        receipt = memory_ledger.list_receipts(connection, result.touched_memory_ids[0])[0]
        queued = memory_extraction.get_job(connection, job.id)
    assert changed == 1
    assert receipt.source_deleted_at == "2026-08-13T11:00:00+00:00"
    assert queued is not None
    assert queued.status == "rejected"
    assert queued.content is None
    assert queued.claim_token is None
    assert queued.last_error_code == "source_deleted"
