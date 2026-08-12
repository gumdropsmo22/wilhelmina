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
        coven_registry.register_pending_member(
            connection,
            guild_id=100,
            user_id=3,
            display_name="Other Member",
            actor_user_id=2,
        )
        memory_ledger.initialize_memory_schema(connection)
    return path


def _add(
    connection,
    *,
    summary: str,
    topic: str,
    category: str = "Interest",
    label: str = "Fact",
    subject_user_id: int = 2,
    actor_user_id: int = 2,
):
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=subject_user_id,
        category=category,
        epistemic_label=label,
        summary=summary,
        topic_key=topic,
        actor_user_id=actor_user_id,
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
    assert summary.subject_receipt_count == 2
    assert summary.authored_cross_subject_receipt_count == 0
    assert summary.restricted_count == 1
    assert summary.admin_only_count == 1


def test_admin_duplicate_can_tighten_privacy_but_never_loosen_it(database_path):
    with managed_connection(database_path) as connection:
        first_result, first_stored = memory_admin.add_admin_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Interest",
            epistemic_label="Fact",
            summary="Keeps a very specific social detail",
            topic_key="interest.private-detail",
            actor_user_id=2,
            privacy_class="ordinary",
            reveal_scope="cross_member",
            importance=50,
        )
        assert first_result.created is True
        assert first_stored.privacy_class == "ordinary"
        assert first_stored.reveal_scope == "cross_member"

        tightened_result, tightened = memory_admin.add_admin_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Interest",
            epistemic_label="Fact",
            summary="Keeps a very specific social detail",
            topic_key="interest.private-detail",
            actor_user_id=2,
            privacy_class="restricted",
            reveal_scope="admin_only",
            importance=90,
        )
        assert tightened_result.created is False
        assert tightened.id == first_stored.id
        assert tightened.privacy_class == "restricted"
        assert tightened.reveal_scope == "admin_only"
        assert tightened.importance == 50

        broader_result, still_tight = memory_admin.add_admin_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Interest",
            epistemic_label="Fact",
            summary="Keeps a very specific social detail",
            topic_key="interest.private-detail",
            actor_user_id=2,
            privacy_class="ordinary",
            reveal_scope="cross_member",
            importance=10,
        )
        assert broader_result.created is False
        assert still_tight.privacy_class == "restricted"
        assert still_tight.reveal_scope == "admin_only"
        assert still_tight.importance == 50
        assert len(memory_ledger.list_receipts(connection, still_tight.id)) == 3


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
        assert memory_ledger.list_profile(
            connection,
            guild_id=100,
            subject_user_id=2,
        ) == []
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
    assert audit_log.deserialize_payload(event.after_json) == {
        "memory_count_deleted": 2,
        "subject_memory_count_deleted": 2,
        "authored_cross_subject_receipt_count_deleted": 0,
        "evidence_orphan_memory_count_deleted": 0,
    }
    assert "astronomy" not in (event.after_json or "").lower()


def test_member_inventory_and_purge_include_cross_subject_authored_receipts(database_path):
    with managed_connection(database_path) as connection:
        shared = _add(
            connection,
            summary="A shared claim with two independent receipts",
            topic="gossip.shared-claim",
            category="Gossip",
            label="Gossip",
            subject_user_id=3,
            actor_user_id=2,
        )
        shared_again = _add(
            connection,
            summary="A shared claim with two independent receipts",
            topic="gossip.shared-claim",
            category="Gossip",
            label="Gossip",
            subject_user_id=3,
            actor_user_id=3,
        )
        assert shared_again.memory.id == shared.memory.id
        assert len(memory_ledger.list_receipts(connection, shared.memory.id)) == 2

        founder_only_evidence = _add(
            connection,
            summary="A second claim supported only by the founder's receipt",
            topic="gossip.founder-only-source",
            category="Gossip",
            label="Gossip",
            subject_user_id=3,
            actor_user_id=2,
        )
        assert len(memory_ledger.list_receipts(connection, founder_only_evidence.memory.id)) == 1

        inventory = memory_admin.summarize_member(
            connection,
            guild_id=100,
            subject_user_id=2,
        )
        assert inventory.memory_count == 0
        assert inventory.subject_receipt_count == 0
        assert inventory.authored_cross_subject_receipt_count == 2
        assert inventory.receipt_count == 2

        result = memory_admin.delete_member_data(
            connection,
            guild_id=100,
            subject_user_id=2,
            actor_user_id=2,
        )

        assert result.subject_memory_count_deleted == 0
        assert result.authored_cross_subject_receipt_count_deleted == 2
        assert result.evidence_orphan_memory_count_deleted == 1
        assert result.memory_count_deleted == 1

        surviving = memory_ledger.get_memory(connection, shared.memory.id)
        assert surviving is not None
        surviving_receipts = memory_ledger.list_receipts(connection, shared.memory.id)
        assert len(surviving_receipts) == 1
        assert surviving_receipts[0].author_user_id == 3
        assert memory_ledger.get_memory(connection, founder_only_evidence.memory.id) is None

        assert coven_registry.get_entry(
            connection,
            guild_id=100,
            user_id=2,
            required=False,
        ) is not None

        event = next(
            event
            for event in audit_log.list_audit_events(connection, 100, limit=30)
            if event.action == "memory.member_deleted"
        )
        payload = audit_log.deserialize_payload(event.after_json)

    assert payload == {
        "memory_count_deleted": 1,
        "subject_memory_count_deleted": 0,
        "authored_cross_subject_receipt_count_deleted": 2,
        "evidence_orphan_memory_count_deleted": 1,
    }
    assert "shared claim" not in (event.after_json or "").lower()
    assert "founder-only" not in (event.after_json or "").lower()
