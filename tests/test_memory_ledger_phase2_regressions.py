from __future__ import annotations

import sqlite3

import pytest

from services import coven_registry, memory_ledger
from services.database import initialize_database, managed_connection


def _bootstrap(path) -> None:
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


def test_ordinary_same_topic_never_replaces_restricted_admin_memory(tmp_path):
    path = tmp_path / "privacy-regression.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        admin = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Admin note",
            epistemic_label="Fact",
            summary="Founder-only context",
            topic_key="shared.topic",
            actor_user_id=2,
        )
        admin_receipts_before = memory_ledger.list_receipts(connection, admin.memory.id)
        assert len(admin_receipts_before) == 1

        ordinary = memory_ledger.add_memory(
            connection,
            guild_id=100,
            subject_user_id=2,
            category="Interest",
            epistemic_label="Fact",
            summary="Publicly usable context",
            topic_key="shared.topic",
            actor_user_id=2,
        )

        preserved_admin = memory_ledger.get_memory(connection, admin.memory.id)
        admin_receipts_after = memory_ledger.list_receipts(connection, admin.memory.id)
        profile = memory_ledger.list_profile(
            connection,
            guild_id=100,
            subject_user_id=2,
        )

    assert ordinary.replaced_memory_ids == ()
    assert preserved_admin is not None
    assert preserved_admin.privacy_class == "restricted"
    assert preserved_admin.reveal_scope == "admin_only"
    assert [receipt.id for receipt in admin_receipts_after] == [
        receipt.id for receipt in admin_receipts_before
    ]
    assert {memory.id for memory in profile} == {admin.memory.id, ordinary.memory.id}


def test_v6_migration_enforces_importance_database_constraint(tmp_path):
    path = tmp_path / "importance-regression.sqlite3"
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
        memory_id = int(
            connection.execute("SELECT id FROM memory_records").fetchone()["id"]
        )

        memory_ledger.initialize_memory_schema(connection)
        migrated = memory_ledger.get_memory(connection, memory_id)
        assert migrated is not None and migrated.importance == 50

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE memory_records SET importance = 101 WHERE id = ?",
                (memory_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE memory_records SET importance = -1 WHERE id = ?",
                (memory_id,),
            )

        still_valid = memory_ledger.get_memory(connection, memory_id)

    assert still_valid is not None
    assert still_valid.importance == 50
