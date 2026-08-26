import sqlite3
from datetime import date

import pytest

from services import audit_log
from services import coven_registry as registry
from services import member_profiles
from services.database import connect, initialize_database, managed_connection
from services.member_identity import MemberIdentityError


def _bootstrap(path, *, guild_id: int = 1) -> None:
    initialize_database(path)
    with managed_connection(path) as connection:
        registry.bootstrap_registry(
            connection,
            guild_id=guild_id,
            wilhelmina_user_id=100 + guild_id,
            founder_user_id=200 + guild_id,
            founder_name="Founder",
            actor_user_id=200 + guild_id,
        )
        registry.register_pending_member(
            connection,
            guild_id=guild_id,
            user_id=300,
            display_name="Old Screen Name",
            actor_user_id=300,
        )


def _profile_columns(connection) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            "PRAGMA table_info(coven_member_identity_profiles)"
        ).fetchall()
    }


def test_identity_persists_both_names_and_full_birth_date(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        stored = member_profiles.save_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            discord_display_name="  xXDarkSylveonXx  ",
            preferred_name="  Jessica  ",
            birth_date="1991-10-31",
            today=date(2026, 8, 6),
            actor_user_id=300,
        )
        context = member_profiles.get_trusted_identity_context(
            connection,
            guild_id=1,
            user_id=300,
            on_date=date(2026, 10, 31),
        )

    assert stored.discord_display_name == "xXDarkSylveonXx"
    assert stored.preferred_name == "Jessica"
    assert stored.birth_date == "1991-10-31"
    assert context.discord_display_name == "xXDarkSylveonXx"
    assert context.preferred_name == "Jessica"
    assert context.birth_date == "1991-10-31"
    assert context.age == 35


def test_identity_survives_a_new_database_connection(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        member_profiles.save_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            discord_display_name="Screen Name",
            preferred_name="Real Name",
            birth_date="1990-01-01",
            today=date(2026, 8, 6),
            actor_user_id=300,
        )

    with managed_connection(path) as connection:
        stored = member_profiles.get_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            required=True,
        )
        eligible = member_profiles.profile_is_memory_eligible(
            connection,
            guild_id=1,
            user_id=300,
        )

    assert stored is not None
    assert stored.discord_display_name == "Screen Name"
    assert stored.preferred_name == "Real Name"
    assert stored.birth_date == "1990-01-01"
    assert eligible is True


def test_underage_profile_does_not_change_registry_name(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        with pytest.raises(MemberIdentityError, match="at least 18"):
            member_profiles.save_member_identity(
                connection,
                guild_id=1,
                user_id=300,
                discord_display_name="Changed Too Soon",
                preferred_name="Member",
                birth_date="2010-01-01",
                today=date(2026, 8, 6),
                actor_user_id=300,
            )
        entry = registry.get_entry(connection, guild_id=1, user_id=300)

    assert entry is not None
    assert entry.display_name == "Old Screen Name"


def test_display_name_refresh_keeps_preferred_name_and_birth_date(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        member_profiles.save_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            discord_display_name="First Screen Name",
            preferred_name="Jessica",
            birth_date="1991-10-31",
            today=date(2026, 8, 6),
            actor_user_id=300,
        )
        member_profiles.refresh_discord_display_name(
            connection,
            guild_id=1,
            user_id=300,
            discord_display_name="Second Screen Name",
            actor_user_id=101,
        )
        stored = member_profiles.get_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            required=True,
        )

    assert stored is not None
    assert stored.discord_display_name == "Second Screen Name"
    assert stored.preferred_name == "Jessica"
    assert stored.birth_date == "1991-10-31"


def test_identity_is_scoped_to_one_guild(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path, guild_id=1)
    _bootstrap(path, guild_id=2)

    with managed_connection(path) as connection:
        member_profiles.save_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            discord_display_name="Guild One",
            preferred_name="Jessica",
            birth_date="1991-10-31",
            today=date(2026, 8, 6),
            actor_user_id=300,
        )
        first = member_profiles.get_member_identity(
            connection,
            guild_id=1,
            user_id=300,
        )
        second = member_profiles.get_member_identity(
            connection,
            guild_id=2,
            user_id=300,
        )

    assert first is not None
    assert second is None


def test_identity_audit_omits_names_and_birth_date(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        member_profiles.save_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            discord_display_name="Secret Screen Name",
            preferred_name="Secret Preferred Name",
            birth_date="1991-10-31",
            today=date(2026, 8, 6),
            actor_user_id=300,
        )
        events = audit_log.list_audit_events_for_target(connection, 1, 300, limit=10)

    identity_event = next(event for event in events if event.action == "identity.save")
    payload = f"{identity_event.before_json}{identity_event.after_json}"
    assert "Secret Screen Name" not in payload
    assert "Secret Preferred Name" not in payload
    assert "1991-10-31" not in payload
    assert "consent" not in payload.lower()


def test_identity_schema_v12_has_no_consent_columns(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        member_profiles.initialize_member_identity_schema(connection)
        columns = _profile_columns(connection)
        versions = {
            int(row["version"])
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }

    assert columns == {
        "guild_id",
        "user_id",
        "preferred_name",
        "birth_date",
        "created_at",
        "updated_at",
    }
    assert "adult_memory_consent_at" not in columns
    assert "memory_consent_version" not in columns
    assert member_profiles.MEMBER_IDENTITY_SCHEMA_VERSION in versions


def test_v7_identity_profile_migrates_to_v12_without_losing_identity(tmp_path) -> None:
    path = tmp_path / "identity-v7.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        connection.execute(
            """
            CREATE TABLE coven_member_identity_profiles (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                preferred_name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                adult_memory_consent_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO coven_member_identity_profiles (
                guild_id, user_id, preferred_name, birth_date,
                adult_memory_consent_at, created_at, updated_at
            )
            VALUES (1, 300, 'Jessica', '1991-10-31', 'old-consent', 'created', 'updated')
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (7, 'old')"
        )

        member_profiles.initialize_member_identity_schema(connection)
        stored = member_profiles.get_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            required=True,
        )
        context = member_profiles.get_trusted_identity_context(
            connection,
            guild_id=1,
            user_id=300,
            on_date=date(2026, 8, 6),
        )
        columns = _profile_columns(connection)

    assert stored is not None
    assert stored.preferred_name == "Jessica"
    assert stored.birth_date == "1991-10-31"
    assert stored.created_at == "created"
    assert stored.updated_at == "updated"
    assert context.birth_date == "1991-10-31"
    assert member_profiles.profile_is_memory_eligible(
        connect(path), guild_id=1, user_id=300
    ) is True
    assert "adult_memory_consent_at" not in columns
    assert "memory_consent_version" not in columns


def test_v8_identity_profile_migrates_to_v12_and_drops_both_consent_columns(tmp_path) -> None:
    path = tmp_path / "identity-v8.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        connection.execute(
            """
            CREATE TABLE coven_member_identity_profiles (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                preferred_name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                adult_memory_consent_at TEXT NOT NULL,
                memory_consent_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO coven_member_identity_profiles (
                guild_id, user_id, preferred_name, birth_date,
                adult_memory_consent_at, memory_consent_version, created_at, updated_at
            )
            VALUES (1, 300, 'Jessica', '1991-10-31', 'old-consent', 'v2', 'created', 'updated')
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (8, 'old')"
        )

        member_profiles.initialize_member_identity_schema(connection)
        stored = member_profiles.get_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            required=True,
        )
        columns = _profile_columns(connection)

    assert stored is not None
    assert stored.preferred_name == "Jessica"
    assert stored.birth_date == "1991-10-31"
    assert stored.created_at == "created"
    assert stored.updated_at == "updated"
    assert "adult_memory_consent_at" not in columns
    assert "memory_consent_version" not in columns


def test_failed_v12_copy_rolls_back_to_intact_legacy_table(tmp_path) -> None:
    path = tmp_path / "identity-bad-legacy.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        connection.execute(
            """
            CREATE TABLE coven_member_identity_profiles (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                preferred_name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                adult_memory_consent_at TEXT NOT NULL,
                memory_consent_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO coven_member_identity_profiles (
                guild_id, user_id, preferred_name, birth_date,
                adult_memory_consent_at, memory_consent_version, created_at, updated_at
            )
            VALUES (1, 300, '', '1991-10-31', 'old-consent', 'v2', 'created', 'updated')
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        with managed_connection(path) as connection:
            member_profiles.initialize_member_identity_schema(connection)

    connection = connect(path)
    try:
        columns = _profile_columns(connection)
        row = connection.execute(
            "SELECT preferred_name, memory_consent_version FROM coven_member_identity_profiles"
        ).fetchone()
        legacy_temp_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (member_profiles.LEGACY_IDENTITY_TABLE,),
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row["preferred_name"] == ""
    assert row["memory_consent_version"] == "v2"
    assert "adult_memory_consent_at" in columns
    assert "memory_consent_version" in columns
    assert legacy_temp_exists is None
