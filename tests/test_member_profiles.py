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


def test_identity_persists_both_names_full_birth_date_and_consent(tmp_path) -> None:
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
            adult_memory_consent=True,
            consent_at="2026-08-06T20:00:00+00:00",
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
    assert stored.adult_memory_consent_at == "2026-08-06T20:00:00+00:00"
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
            adult_memory_consent=True,
            actor_user_id=300,
        )

    with managed_connection(path) as connection:
        stored = member_profiles.get_member_identity(
            connection,
            guild_id=1,
            user_id=300,
            required=True,
        )

    assert stored is not None
    assert stored.discord_display_name == "Screen Name"
    assert stored.preferred_name == "Real Name"
    assert stored.birth_date == "1990-01-01"


def test_adult_memory_consent_is_required(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        with pytest.raises(MemberIdentityError, match="consent"):
            member_profiles.save_member_identity(
                connection,
                guild_id=1,
                user_id=300,
                discord_display_name="Screen Name",
                preferred_name="Real Name",
                birth_date="1990-01-01",
                today=date(2026, 8, 6),
                adult_memory_consent=False,
                actor_user_id=300,
            )
        stored = member_profiles.get_member_identity(
            connection,
            guild_id=1,
            user_id=300,
        )

    assert stored is None


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
                adult_memory_consent=True,
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
            adult_memory_consent=True,
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
            adult_memory_consent=True,
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
            adult_memory_consent=True,
            actor_user_id=300,
        )
        events = audit_log.list_audit_events_for_target(connection, 1, 300, limit=10)

    identity_event = next(event for event in events if event.action == "identity.save")
    payload = f"{identity_event.before_json}{identity_event.after_json}"
    assert "Secret Screen Name" not in payload
    assert "Secret Preferred Name" not in payload
    assert "1991-10-31" not in payload


def test_identity_schema_version_and_table_are_created(tmp_path) -> None:
    path = tmp_path / "identity.sqlite3"
    _bootstrap(path)

    with managed_connection(path) as connection:
        member_profiles.initialize_member_identity_schema(connection)

    connection = connect(path)
    try:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'coven_member_identity_profiles'
            """
        ).fetchone()
        versions = {
            int(row["version"])
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
    finally:
        connection.close()

    assert table is not None
    assert member_profiles.MEMBER_IDENTITY_SCHEMA_VERSION in versions
