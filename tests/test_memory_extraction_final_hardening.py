from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services import memory_extraction, memory_ledger
from services.database import initialize_database, managed_connection


@pytest.mark.parametrize(
    "text",
    [
        "I have leukemia",
        "I have hypertension",
        "I have hepatitis C",
        "I have rheumatoid arthritis",
        "I have dementia",
        "I suffer from migraines",
        "I suffer with anorexia nervosa",
        "I have bipolar disorder",
        "I take medication for ADHD",
        "I hooked up with my ex last night",
        "I think the mayor is useless",
        "I am Muslim",
        "I am bisexual",
        "I got drunk at the party",
        "I lied about why I missed work",
    ],
)
def test_socially_sensitive_content_is_not_blocked_before_extraction(text):
    assert memory_extraction.guard_extractable_text(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "driver licence D1234567",
        "auth token: abcdefgh123456",
        "password: hunter2hunter2",
        "My API key is sk-abcdefghijklmnopqrstuvwxyz1234567890",
        "Ship it to 123 Main Street",
        "Card 4111 1111 1111 1111",
    ],
)
def test_actual_secrets_and_identifiers_remain_blocked_before_extraction(text):
    with pytest.raises(memory_ledger.BlockedMemoryContent):
        memory_extraction.guard_extractable_text(text)


def test_base_memory_ledger_no_longer_blocks_diagnosis_language():
    text = "I was diagnosed with Crohn's disease"
    assert memory_ledger.validate_extractable_text(text) == text


@pytest.mark.parametrize(
    "content",
    [
        "I have rheumatoid arthritis",
        "I suffer with anorexia nervosa",
        "I have bipolar disorder",
        "I take medication for ADHD",
    ],
)
def test_sensitive_social_content_can_enter_queue_when_other_gates_allow(tmp_path, content):
    path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(path)

    with managed_connection(path) as connection:
        memory_extraction.initialize_extraction_schema(connection)
        queued = memory_extraction.enqueue_message(
            connection,
            guild_id=100,
            subject_user_id=2,
            source_context="guild",
            author_user_id=2,
            channel_id=10,
            message_id=501,
            jump_url="https://discord.com/channels/100/10/501",
            content=content,
            source_created_at="2026-08-17T02:00:00+00:00",
        )
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_extraction_jobs"
        ).fetchone()["count"]

    assert queued.content == content
    assert count == 1


@pytest.mark.parametrize(
    "candidate",
    [
        {
            "category": "Identity",
            "epistemic_label": "Fact",
            "summary": "I have hepatitis C",
            "topic_key": "health.private",
            "importance": 60,
            "confidence": 95,
            "entities": [],
        },
        {
            "category": "Identity",
            "epistemic_label": "Fact",
            "summary": "Lives with dementia",
            "topic_key": "I have dementia",
            "importance": 60,
            "confidence": 95,
            "entities": [],
        },
        {
            "category": "Identity",
            "epistemic_label": "Fact",
            "summary": "Gets migraines",
            "topic_key": "health.migraines",
            "importance": 60,
            "confidence": 95,
            "entities": [{"type": "term", "key": "I suffer from migraines"}],
        },
        {
            "category": "Identity",
            "epistemic_label": "Fact",
            "summary": "I suffer with anorexia nervosa",
            "topic_key": "health.private",
            "importance": 60,
            "confidence": 95,
            "entities": [],
        },
    ],
)
def test_sensitive_social_content_is_not_rejected_from_model_output(candidate):
    proposal = memory_extraction.parse_proposal({"candidates": [candidate]})
    assert len(proposal.candidates) == 1


def test_source_edit_ordering_preserves_subsecond_precision():
    normalized = memory_extraction.normalize_source_timestamp(
        "2026-08-17T02:00:00.123456+00:00"
    )
    assert normalized == "2026-08-17T02:00:00.123456+00:00"

    job = memory_extraction.ExtractionJob(
        id=1,
        guild_id=100,
        subject_user_id=2,
        source_context="guild",
        author_user_id=2,
        channel_id=10,
        message_id=500,
        jump_url="https://discord.com/channels/100/10/500",
        content="latest",
        content_hash="hash",
        source_created_at="2026-08-17T01:59:00.000000+00:00",
        source_edited_at="2026-08-17T02:00:00.100000+00:00",
        status="pending",
        attempts=0,
        available_at="2026-08-17T02:00:00+00:00",
        lease_expires_at=None,
        claim_token=None,
        last_error_code=None,
        created_at="2026-08-17T02:00:00+00:00",
        updated_at="2026-08-17T02:00:00+00:00",
    )

    assert memory_extraction.source_edit_is_newer(
        job, "2026-08-17T02:00:00.200000+00:00"
    )
    assert not memory_extraction.source_edit_is_newer(
        job, "2026-08-17T02:00:00.050000+00:00"
    )


def test_final_ttl_gate_revokes_processing_claim_before_apply(tmp_path, monkeypatch):
    path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(path)

    before_expiry = datetime(2026, 8, 17, 0, 59, 59, tzinfo=UTC)
    after_expiry = datetime(2026, 8, 17, 1, 0, 0, 500001, tzinfo=UTC)
    monkeypatch.setattr(memory_extraction, "_now", lambda: before_expiry)

    with managed_connection(path) as connection:
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
            source_created_at="2026-08-17T00:00:00.500000+00:00",
            source_edited_at="2026-08-17T00:00:00.500000+00:00",
        )
        connection.execute(
            "UPDATE memory_extraction_jobs SET available_at = ? WHERE id = ?",
            ("2026-08-17T00:59:58+00:00", queued.id),
        )
        claimed = memory_extraction.claim_next_job(connection)
        assert claimed is not None
        assert claimed.status == "processing"
        assert claimed.claim_token

        monkeypatch.setattr(memory_extraction, "_now", lambda: after_expiry)
        expired = memory_extraction.expire_stale_jobs(connection)
        current = memory_extraction.get_job(connection, queued.id)

    assert expired == 1
    assert current is not None
    assert current.status == "rejected"
    assert current.content is None
    assert current.claim_token is None
    assert current.last_error_code == "queue_expired"
