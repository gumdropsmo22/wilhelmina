from __future__ import annotations

import pytest

from services import audit_log, coven_registry, memory_admin, memory_ledger
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


def _add(connection, *, summary: str, topic: str, category: str = "Interest", label: str = "Fact"):
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=2,
        category=category,
        epistemic_label=label,
        summary=summary,
        topic_key=topic,
        actor_user_id=2,
        source_context="admin",
    )


def test_admin_summary_is_content_free_and_reports_integrity(database_path):
    with managed_connection(database_path) as connection:
        _add(connection, summary="Likes astronomy", topic="interest.astronomy")
        _add(
            connection,
            summary="Founder-only moderation note",
            topic="admin.moderation",
            category="Admin note",
        )
        _add(
            connection,
            summary="Someone claims Alex quit",
            topic="alex.project.departure",
            category="Gossip",
            label="Gossip",
        )
        summary = memory_admin.summarize_ledger(connection, guild_id=100)

    assert summary.total_records == 3
    assert summary.active_records == 3
    assert summary.subject_count == 1
    assert summary.receipt_count == 3
    assert summary.gossip_records == 1
    assert summary.restricted_records == 1
    assert summary.admin_only_records == 1
    assert summary.integrity.ok is True


def test_member_summary_counts_private_rows_without_returning_content(database_path):
    with managed_connection(database_path) as connection:
        _add(connection, summary="Likes astronomy", topic="interest.astronomy")
        _add(
            connection,
            summary="Founder-only moderation note",
            topic="admin.moderation",
            category="Admin note",
        )
        summary = memory_admin.summarize_member(
            connection,
            guild_id=100,
            subject_user_id=2,
        )

    assert summary.memory_count == 2
    assert summary.receipt_count == 2
    assert summary.restricted_count == 1
    assert summary.admin_only_count == 1


def test_delete_member_memories_cascades_evidence_and_keeps_registry(database_path):
    with managed_connection(database_path) as connection:
        first = _add(connection, summary="Likes astronomy", topic="interest.astronomy")
        _add(connection, summary="Likes telescopes", topic="interest.telescopes")
        assert len(memory_ledger.list_receipts(connection, first.memory.id)) == 1

        deleted = memory_admin.delete_member_memories(
            connection,
            guild_id=100,
            subject_user_id=2,
            actor_user_id=2,
        )

        assert deleted == 2
        assert memory_ledger.list_profile(connection, guild_id=100, subject_user_id=2) == []
        assert memory_ledger.search_memories(
            connection,
            guild_id=100,
            query="astronomy",
            reveal_scopes=memory_ledger.VALID_REVEAL_SCOPES,
        ) == []
        assert connection.execute(
            "SELECT COUNT(*) AS count FROM memory_receipts WHERE guild_id = 100"
        ).fetchone()["count"] == 0
        assert coven_registry.get_entry(
            connection,
            guild_id=100,
            user_id=2,
            required=False,
        ) is not None

        events = audit_log.list_audit_events(connection, 100, limit=20)
        event = next(event for event in events if event.action == "memory.member_deleted")

    assert event.target == "member:2"
    assert event.before_json is None
    assert audit_log.deserialize_payload(event.after_json) == {"memory_count_deleted": 2}
    assert "astronomy" not in (event.after_json or "").lower()
