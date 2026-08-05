from __future__ import annotations

import sqlite3

import pytest

from services import audit_log, coven_registry, memory_ledger
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


def test_schema_initializes_idempotently(database_path):
    with managed_connection(database_path) as connection:
        memory_ledger.initialize_memory_schema(connection)
        memory_ledger.initialize_memory_schema(connection)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert {
        "memory_ledger_settings",
        "memory_records",
        "memory_receipts",
        "memory_contradictions",
    }.issubset(tables)
    assert memory_ledger.MEMORY_SCHEMA_VERSION in [int(row["version"]) for row in versions]


def test_settings_default_active_and_persist_pause(database_path):
    with managed_connection(database_path) as connection:
        settings = memory_ledger.get_or_create_settings(connection, 100)
        assert settings.collection_enabled is True

        paused = memory_ledger.set_collection_enabled(
            connection, guild_id=100, enabled=False, actor_user_id=2
        )
        assert paused.collection_enabled is False

    with managed_connection(database_path) as connection:
        persisted = memory_ledger.get_or_create_settings(connection, 100)
        assert persisted.collection_enabled is False


def test_designated_channel_persists(database_path):
    with managed_connection(database_path) as connection:
        settings = memory_ledger.set_wilhelmina_channel(
            connection, guild_id=100, channel_id=555, actor_user_id=2
        )
        assert settings.wilhelmina_channel_id == 555

    with managed_connection(database_path) as connection:
        assert memory_ledger.get_or_create_settings(connection, 100).wilhelmina_channel_id == 555


def test_duplicate_memory_merges_discord_receipts(database_path):
    kwargs = dict(
        guild_id=100,
        subject_user_id=2,
        category="Preference",
        epistemic_label="Fact",
        summary="Prefers black coffee",
        actor_user_id=2,
    )
    with managed_connection(database_path) as connection:
        first = memory_ledger.add_memory(
            connection,
            **kwargs,
            author_user_id=2,
            channel_id=10,
            message_id=1000,
            jump_url="https://discord.com/channels/100/10/1000",
            excerpt="I prefer black coffee.",
            source_created_at="2026-07-27T00:00:00+00:00",
        )
        second = memory_ledger.add_memory(
            connection,
            **kwargs,
            author_user_id=2,
            channel_id=11,
            message_id=1001,
            jump_url="https://discord.com/channels/100/11/1001",
            excerpt="Black coffee, obviously.",
            source_created_at="2026-07-27T01:00:00+00:00",
        )

        assert first.created is True
        assert second.created is False
        assert second.merged is True
        assert second.memory.id == first.memory.id
        receipts = memory_ledger.list_receipts(connection, first.memory.id)
        assert len(receipts) == 2
        assert all(receipt.source_kind == "discord" for receipt in receipts)


def test_admin_memory_gets_admin_receipt(database_path):
    with managed_connection(database_path) as connection:
        created = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Admin note",
            epistemic_label="Fact",
            summary="Founder-added note",
            actor_user_id=2,
        )
        receipts = memory_ledger.list_receipts(connection, created.memory.id)

    assert len(receipts) == 1
    assert receipts[0].source_kind == "admin"
    assert receipts[0].message_id is None
    assert receipts[0].channel_id is None
    assert receipts[0].jump_url is None


def test_new_normal_memory_permanently_replaces_old_same_category(database_path):
    with managed_connection(database_path) as connection:
        old = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Preference",
            epistemic_label="Fact",
            summary="Prefers tea",
            actor_user_id=2,
        )
        new = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Preference",
            epistemic_label="Fact",
            summary="Prefers coffee",
            actor_user_id=2,
        )

        assert new.replaced_memory_ids == (old.memory.id,)
        assert memory_ledger.get_memory(connection, old.memory.id, required=False) is None
        assert memory_ledger.list_receipts(connection, old.memory.id) == []
        active = memory_ledger.list_profile(connection, guild_id=100, subject_user_id=2)
        assert [record.summary for record in active] == ["Prefers coffee"]

        events = audit_log.list_audit_events_for_target(
            connection, 100, f"memory:{old.memory.id}"
        )
        replacement = next(event for event in events if event.action == "memory.replaced")
        assert replacement.before_json is None
        assert replacement.after_json is None


def test_conflicting_gossip_is_preserved_and_linked(database_path):
    with managed_connection(database_path) as connection:
        first = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Gossip",
            epistemic_label="Gossip",
            summary="Sam says Alex quit the project",
            topic_key="alex.project.departure",
            actor_user_id=2,
        )
        second = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Gossip",
            epistemic_label="Gossip",
            summary="Jordan says Alex was removed from the project",
            topic_key="alex.project.departure",
            actor_user_id=2,
        )

        profile = memory_ledger.list_profile(connection, guild_id=100, subject_user_id=2)
        links = memory_ledger.list_contradictions(connection)

    assert first.memory.id != second.memory.id
    assert len(profile) == 2
    assert all(record.is_gossip for record in profile)
    assert len(links) == 1
    assert {links[0].left_memory_id, links[0].right_memory_id} == {
        first.memory.id,
        second.memory.id,
    }


def test_deleting_gossip_cascades_contradiction_link(database_path):
    with managed_connection(database_path) as connection:
        first = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Gossip",
            epistemic_label="Gossip",
            summary="First claim",
            topic_key="shared.topic",
            actor_user_id=2,
        )
        memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Gossip",
            epistemic_label="Gossip",
            summary="Second claim",
            topic_key="shared.topic",
            actor_user_id=2,
        )
        assert len(memory_ledger.list_contradictions(connection)) == 1

        memory_ledger.delete_memory(
            connection, memory_id=first.memory.id, actor_user_id=2
        )
        assert memory_ledger.list_contradictions(connection) == []


def test_delete_is_permanent_and_audit_contains_no_content(database_path):
    with managed_connection(database_path) as connection:
        created = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Boundary",
            epistemic_label="Fact",
            summary="Do not mention spiders",
            actor_user_id=2,
            author_user_id=2,
            channel_id=10,
            message_id=1000,
            jump_url="https://discord.com/channels/100/10/1000",
            excerpt="Do not mention spiders.",
            source_created_at="2026-07-27T00:00:00+00:00",
        )
        memory_ledger.delete_memory(
            connection, memory_id=created.memory.id, actor_user_id=2
        )

        assert memory_ledger.get_memory(connection, created.memory.id, required=False) is None
        assert memory_ledger.list_receipts(connection, created.memory.id) == []
        events = audit_log.list_audit_events_for_target(
            connection, 100, f"memory:{created.memory.id}"
        )
        deletion = next(event for event in events if event.action == "memory.deleted")
        assert deletion.before_json is None
        assert deletion.after_json is None


def test_receipt_tracks_edit_and_delete_without_erasing_excerpt(database_path):
    with managed_connection(database_path) as connection:
        created = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Interest",
            epistemic_label="Fact",
            summary="Interested in astronomy",
            actor_user_id=2,
            author_user_id=2,
            channel_id=10,
            message_id=1000,
            jump_url="https://discord.com/channels/100/10/1000",
            excerpt="I like astronomy.",
            source_created_at="2026-07-27T00:00:00+00:00",
        )
        assert memory_ledger.mark_message_edited(
            connection,
            guild_id=100,
            message_id=1000,
            edited_excerpt="I love astronomy.",
            edited_at="2026-07-27T00:05:00+00:00",
        ) == 1
        assert memory_ledger.mark_message_deleted(
            connection,
            guild_id=100,
            message_id=1000,
            deleted_at="2026-07-27T00:10:00+00:00",
        ) == 1

        receipt = memory_ledger.list_receipts(connection, created.memory.id)[0]
        assert receipt.original_excerpt == "I like astronomy."
        assert receipt.edited_excerpt == "I love astronomy."
        assert receipt.source_deleted_at == "2026-07-27T00:10:00+00:00"


def test_prohibited_content_is_rejected_before_extraction(database_path):
    with pytest.raises(memory_ledger.BlockedMemoryContent):
        memory_ledger.validate_extractable_text("My password is hunter2")

    with managed_connection(database_path) as connection:
        with pytest.raises(memory_ledger.BlockedMemoryContent):
            memory_ledger.add_memory(
                connection,
                guild_id=100,
                subject_user_id=2,
                category="Admin note",
                epistemic_label="Fact",
                summary="Their password is hunter2",
                actor_user_id=2,
            )


def test_legacy_member_opt_out_is_inert(database_path):
    with managed_connection(database_path) as connection:
        connection.execute(
            "UPDATE coven_profile_shells SET memory_opt_out = 1 WHERE guild_id = 100 AND user_id = 2"
        )
        created = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Interest",
            epistemic_label="Fact",
            summary="Likes old horror films",
            actor_user_id=2,
        )

    assert created.created is True


def test_profile_foreign_key_requires_registry_shell(database_path):
    with managed_connection(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            memory_ledger.add_memory(
                connection,
                guild_id=100,
                subject_user_id=404,
                category="Interest",
                epistemic_label="Fact",
                summary="Unknown member interest",
                actor_user_id=2,
            )


def test_prompt_renderer_labels_gossip(database_path):
    with managed_connection(database_path) as connection:
        memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Gossip",
            epistemic_label="Gossip",
            summary="Sam claims Alex stole the charger",
            actor_user_id=2,
        )
        profile = memory_ledger.list_profile(connection, guild_id=100, subject_user_id=2)

    rendered = memory_ledger.render_profile_for_prompt(profile)
    assert "Unverified gossip" in rendered
    assert "Sam claims Alex stole the charger" in rendered
