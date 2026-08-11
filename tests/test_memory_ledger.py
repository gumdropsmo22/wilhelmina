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


def _add(
    connection,
    *,
    summary: str,
    topic: str,
    category: str = "Interest",
    label: str = "Fact",
    **kwargs,
):
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=2,
        category=category,
        epistemic_label=label,
        summary=summary,
        topic_key=topic,
        actor_user_id=2,
        **kwargs,
    )


def test_schema_v9_initializes_idempotently(database_path):
    with managed_connection(database_path) as connection:
        memory_ledger.initialize_memory_schema(connection)
        memory_ledger.initialize_memory_schema(connection)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        record_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(memory_records)").fetchall()
        }
        receipt_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(memory_receipts)").fetchall()
        }
        versions = {
            int(row["version"])
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }

    assert {"memory_records", "memory_receipts", "memory_entities", "memory_search"} <= tables
    assert {"privacy_class", "reveal_scope", "importance"} <= record_columns
    assert "source_context" in receipt_columns
    assert memory_ledger.MEMORY_SCHEMA_VERSION in versions


def test_settings_and_designated_channel_persist(database_path):
    with managed_connection(database_path) as connection:
        assert memory_ledger.get_or_create_settings(connection, 100).collection_enabled is True
        memory_ledger.set_collection_enabled(
            connection, guild_id=100, enabled=False, actor_user_id=2
        )
        memory_ledger.set_wilhelmina_channel(
            connection, guild_id=100, channel_id=555, actor_user_id=2
        )

    with managed_connection(database_path) as connection:
        settings = memory_ledger.get_or_create_settings(connection, 100)
        assert settings.collection_enabled is False
        assert settings.wilhelmina_channel_id == 555


def test_duplicate_memory_merges_guild_receipts(database_path):
    with managed_connection(database_path) as connection:
        first = _add(
            connection,
            summary="Prefers black coffee",
            topic="drink.coffee.preference",
            category="Preference",
            author_user_id=2,
            channel_id=10,
            message_id=1000,
            jump_url="https://discord.com/channels/100/10/1000",
            excerpt="I prefer black coffee.",
            source_created_at="2026-07-27T00:00:00+00:00",
        )
        second = _add(
            connection,
            summary="Prefers black coffee",
            topic="drink.coffee.preference",
            category="Preference",
            author_user_id=2,
            channel_id=11,
            message_id=1001,
            jump_url="https://discord.com/channels/100/11/1001",
            excerpt="Black coffee, obviously.",
            source_created_at="2026-07-27T01:00:00+00:00",
        )
        receipts = memory_ledger.list_receipts(connection, first.memory.id)

    assert first.created is True
    assert second.created is False and second.merged is True
    assert second.memory.id == first.memory.id
    assert len(receipts) == 2
    assert {receipt.source_context for receipt in receipts} == {"guild"}


def test_dm_receipt_keeps_evidence_without_fake_jump_url(database_path):
    with managed_connection(database_path) as connection:
        created = _add(
            connection,
            summary="Is thinking about texting Alex again",
            topic="relationship.alex.recontact",
            category="Relationship context",
            author_user_id=2,
            message_id=5000,
            excerpt="I might text Alex again.",
            source_created_at="2026-08-11T12:00:00+00:00",
            source_context="dm",
        )
        receipt = memory_ledger.list_receipts(connection, created.memory.id)[0]

    assert receipt.source_kind == "discord"
    assert receipt.source_context == "dm"
    assert receipt.message_id == 5000
    assert receipt.channel_id is None
    assert receipt.jump_url is None


def test_admin_notes_are_restricted_and_admin_only(database_path):
    with managed_connection(database_path) as connection:
        created = _add(
            connection,
            summary="Founder-added note",
            topic="admin.founder.note",
            category="Admin note",
        )
        receipt = memory_ledger.list_receipts(connection, created.memory.id)[0]

    assert created.memory.privacy_class == "restricted"
    assert created.memory.reveal_scope == "admin_only"
    assert receipt.source_kind == "admin"
    assert receipt.source_context == "admin"


def test_topic_scoped_replacement_preserves_unrelated_same_category(database_path):
    with managed_connection(database_path) as connection:
        old = _add(
            connection,
            summary="Prefers tea",
            topic="drink.hot.preference",
            category="Preference",
        )
        unrelated = _add(
            connection,
            summary="Prefers horror movies",
            topic="movie.genre.preference",
            category="Preference",
        )
        new = _add(
            connection,
            summary="Prefers coffee",
            topic="drink.hot.preference",
            category="Preference",
        )
        profile = memory_ledger.list_profile(connection, guild_id=100, subject_user_id=2)

    assert new.replaced_memory_ids == (old.memory.id,)
    assert {memory.summary for memory in profile} == {"Prefers coffee", "Prefers horror movies"}
    assert unrelated.memory.id in {memory.id for memory in profile}


def test_gossip_links_rebuild_when_topic_changes(database_path):
    with managed_connection(database_path) as connection:
        first = _add(
            connection,
            summary="Sam says Alex quit",
            topic="alex.project.departure",
            category="Gossip",
            label="Gossip",
        )
        second = _add(
            connection,
            summary="Jordan says Alex was removed",
            topic="alex.project.departure",
            category="Gossip",
            label="Gossip",
        )
        links = memory_ledger.list_contradictions(connection)
        assert len(links) == 1
        assert {links[0].left_memory_id, links[0].right_memory_id} == {
            first.memory.id,
            second.memory.id,
        }

        memory_ledger.update_memory(
            connection,
            memory_id=second.memory.id,
            actor_user_id=2,
            topic_key="alex.project.removal",
        )
        assert memory_ledger.list_contradictions(connection) == []


def test_delete_cascades_receipts_entities_fts_and_contradictions(database_path):
    with managed_connection(database_path) as connection:
        first = _add(
            connection,
            summary="First telescope claim",
            topic="astronomy.telescope.claim",
            category="Gossip",
            label="Gossip",
        )
        _add(
            connection,
            summary="Second telescope claim",
            topic="astronomy.telescope.claim",
            category="Gossip",
            label="Gossip",
        )
        memory_ledger.set_memory_entities(
            connection,
            memory_id=first.memory.id,
            entities=(("term", "telescope"),),
        )
        assert memory_ledger.search_memories(
            connection, guild_id=100, query="telescope"
        )
        assert memory_ledger.find_memories_by_entity(
            connection,
            guild_id=100,
            entity_type="term",
            entity_key="telescope",
        )
        assert memory_ledger.list_contradictions(connection)

        memory_ledger.delete_memory(
            connection, memory_id=first.memory.id, actor_user_id=2
        )

        assert memory_ledger.list_receipts(connection, first.memory.id) == []
        assert memory_ledger.list_memory_entities(connection, memory_id=first.memory.id) == []
        assert all(
            link.left_memory_id != first.memory.id and link.right_memory_id != first.memory.id
            for link in memory_ledger.list_contradictions(connection)
        )
        assert memory_ledger.find_memories_by_entity(
            connection,
            guild_id=100,
            entity_type="term",
            entity_key="telescope",
        ) == []
        assert memory_ledger.check_memory_integrity(connection).ok is True


def test_memory_audits_never_serialize_memory_content(database_path):
    phrase = "collects haunted porcelain clowns"
    with managed_connection(database_path) as connection:
        created = _add(
            connection,
            summary=phrase,
            topic="hobby.clowns",
        )
        memory_ledger.update_memory(
            connection,
            memory_id=created.memory.id,
            actor_user_id=2,
            summary="collects haunted dolls",
        )
        events = audit_log.list_audit_events_for_target(
            connection, 100, f"memory:{created.memory.id}"
        )

    serialized = "\n".join(
        value or ""
        for event in events
        for value in (event.before_json, event.after_json)
    )
    assert phrase not in serialized
    assert "haunted dolls" not in serialized


def test_receipt_tracks_edit_and_source_delete(database_path):
    with managed_connection(database_path) as connection:
        created = _add(
            connection,
            summary="Interested in astronomy",
            topic="interest.astronomy",
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


def test_prohibited_content_is_rejected_before_memory_or_extraction(database_path):
    with pytest.raises(memory_ledger.BlockedMemoryContent):
        memory_ledger.validate_extractable_text("My password is hunter2")

    with managed_connection(database_path) as connection:
        with pytest.raises(memory_ledger.BlockedMemoryContent):
            _add(
                connection,
                summary="Their password is hunter2",
                topic="admin.secret",
                category="Admin note",
            )


def test_legacy_member_opt_out_remains_inert(database_path):
    with managed_connection(database_path) as connection:
        connection.execute(
            "UPDATE coven_profile_shells SET memory_opt_out = 1 WHERE guild_id = 100 AND user_id = 2"
        )
        created = _add(
            connection,
            summary="Likes old horror films",
            topic="movie.horror",
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


def test_search_and_entity_lookup_respect_reveal_scope(database_path):
    with managed_connection(database_path) as connection:
        social = _add(
            connection,
            summary="Obsessed with lunar eclipses",
            topic="astronomy.lunar.eclipse",
        )
        owner_only = _add(
            connection,
            summary="Keeps a private eclipse journal",
            topic="astronomy.eclipse.journal",
            reveal_scope="owner_only",
        )
        memory_ledger.set_memory_entities(
            connection,
            memory_id=social.memory.id,
            entities=(("term", "eclipse"),),
        )
        memory_ledger.set_memory_entities(
            connection,
            memory_id=owner_only.memory.id,
            entities=(("term", "eclipse"),),
        )

        default_hits = memory_ledger.search_memories(
            connection, guild_id=100, query="eclipse"
        )
        owner_hits = memory_ledger.search_memories(
            connection,
            guild_id=100,
            query="eclipse",
            reveal_scopes=("cross_member", "owner_only"),
        )
        entity_hits = memory_ledger.find_memories_by_entity(
            connection,
            guild_id=100,
            entity_type="term",
            entity_key="eclipse",
        )

    assert [hit.memory.id for hit in default_hits] == [social.memory.id]
    assert {hit.memory.id for hit in owner_hits} == {social.memory.id, owner_only.memory.id}
    assert [memory.id for memory in entity_hits] == [social.memory.id]
    assert memory_ledger.memory_is_revealable(owner_only.memory, interlocutor_user_id=2)
    assert not memory_ledger.memory_is_revealable(owner_only.memory, interlocutor_user_id=3)


def test_fts_tracks_memory_updates(database_path):
    with managed_connection(database_path) as connection:
        created = _add(
            connection,
            summary="Collects vinyl records",
            topic="music.vinyl",
        )
        assert memory_ledger.search_memories(connection, guild_id=100, query="vinyl")
        memory_ledger.update_memory(
            connection,
            memory_id=created.memory.id,
            actor_user_id=2,
            summary="Collects cassette tapes",
            topic_key="music.cassettes",
        )
        assert memory_ledger.search_memories(connection, guild_id=100, query="vinyl") == []
        hits = memory_ledger.search_memories(connection, guild_id=100, query="cassettes")
        assert [hit.memory.id for hit in hits] == [created.memory.id]


def test_prompt_renderer_preserves_gossip_label(database_path):
    with managed_connection(database_path) as connection:
        _add(
            connection,
            summary="Sam claims Alex stole the charger",
            topic="alex.charger",
            category="Gossip",
            label="Gossip",
        )
        profile = memory_ledger.list_profile(connection, guild_id=100, subject_user_id=2)
    rendered = memory_ledger.render_profile_for_prompt(profile)
    assert "Unverified gossip" in rendered
    assert "Sam claims Alex stole the charger" in rendered


def test_v6_schema_migrates_forward_without_losing_existing_memory(tmp_path):
    path = tmp_path / "legacy.sqlite3"
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
        connection.execute(
            """
            CREATE TABLE memory_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                subject_user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                epistemic_label TEXT NOT NULL,
                summary TEXT NOT NULL,
                normalized_key TEXT NOT NULL,
                topic_key TEXT NOT NULL,
                is_gossip INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_confirmed_at TEXT NOT NULL,
                FOREIGN KEY (guild_id, subject_user_id)
                    REFERENCES coven_profile_shells (guild_id, user_id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE memory_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                source_kind TEXT NOT NULL,
                author_user_id INTEGER NOT NULL,
                channel_id INTEGER,
                message_id INTEGER,
                jump_url TEXT,
                original_excerpt TEXT NOT NULL,
                edited_excerpt TEXT,
                source_created_at TEXT NOT NULL,
                source_edited_at TEXT,
                source_deleted_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (memory_id) REFERENCES memory_records (id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            INSERT INTO memory_records (
                guild_id, subject_user_id, category, epistemic_label, summary,
                normalized_key, topic_key, is_gossip, active, created_by,
                created_at, updated_at, last_confirmed_at
            ) VALUES (
                100, 2, 'Interest', 'Fact', 'Likes astronomy', 'legacy-key',
                'interest.astronomy', 0, 1, 2,
                '2026-07-01T00:00:00+00:00',
                '2026-07-01T00:00:00+00:00',
                '2026-07-01T00:00:00+00:00'
            )
            """
        )
        memory_id = int(connection.execute("SELECT id FROM memory_records").fetchone()["id"])
        connection.execute(
            """
            INSERT INTO memory_receipts (
                memory_id, guild_id, source_kind, author_user_id, channel_id,
                message_id, jump_url, original_excerpt, source_created_at, created_at
            ) VALUES (?, 100, 'discord', 2, 10, 1000,
                'https://discord.com/channels/100/10/1000', 'I like astronomy.',
                '2026-07-01T00:00:00+00:00', '2026-07-01T00:00:00+00:00')
            """,
            (memory_id,),
        )

        memory_ledger.initialize_memory_schema(connection)
        migrated = memory_ledger.get_memory(connection, memory_id)
        receipt = memory_ledger.list_receipts(connection, memory_id)[0]
        entities = memory_ledger.list_memory_entities(connection, memory_id=memory_id)
        hits = memory_ledger.search_memories(connection, guild_id=100, query="astronomy")
        integrity = memory_ledger.check_memory_integrity(connection)

    assert migrated is not None and migrated.summary == "Likes astronomy"
    assert migrated.privacy_class == "ordinary"
    assert migrated.reveal_scope == "cross_member"
    assert migrated.importance == 50
    assert receipt.source_context == "guild"
    assert {entity.entity_type for entity in entities} == {"subject", "topic"}
    assert [hit.memory.id for hit in hits] == [memory_id]
    assert integrity.ok is True
