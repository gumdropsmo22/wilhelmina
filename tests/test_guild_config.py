import pytest

from services.database import initialize_database, managed_connection
from services.guild_config import (
    InvalidGuildConfigField,
    InvalidGuildConfigValue,
    clear_guild_config,
    ensure_guild_config,
    get_guild_config,
    set_channel,
    set_role,
    set_timezone,
    validate_guild_config,
)


def test_guild_config_crud_and_partial_clear(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        created = ensure_guild_config(connection, 123)
        assert created.guild_id == 123
        assert created.timezone == "UTC"

        before, after = set_role(connection, 123, "admin_role_id", 456)
        assert before is not None
        assert before.admin_role_id is None
        assert after.admin_role_id == 456

        _, after = set_channel(connection, 123, "welcome_channel_id", 789)
        assert after.welcome_channel_id == 789

        _, after = set_timezone(connection, 123, "Asia/Riyadh")
        assert after.timezone == "Asia/Riyadh"

        before, after = clear_guild_config(connection, 123, ["admin_role_id", "timezone"])
        assert before is not None
        assert after is not None
        assert before.admin_role_id == 456
        assert after.admin_role_id is None
        assert after.timezone == "UTC"

        stored = get_guild_config(connection, 123)
        assert stored is not None
        assert stored.welcome_channel_id == 789


def test_full_clear_deletes_config_row(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        ensure_guild_config(connection, 123)
        before, after = clear_guild_config(connection, 123)
        assert before is not None
        assert after is None
        assert get_guild_config(connection, 123) is None


def test_invalid_fields_and_values_are_rejected(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        with pytest.raises(InvalidGuildConfigField):
            set_role(connection, 123, "owner_role_id", 456)

        with pytest.raises(InvalidGuildConfigValue):
            set_channel(connection, 123, "welcome_channel_id", 0)

        with pytest.raises(InvalidGuildConfigValue):
            set_timezone(connection, 123, "Not/AZone")


def test_validate_guild_config_reports_missing_objects(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        set_role(connection, 123, "admin_role_id", 456)
        set_channel(connection, 123, "welcome_channel_id", 789)
        config = get_guild_config(connection, 123)

    assert config is not None
    issues = validate_guild_config(
        config,
        role_exists=lambda role_id: role_id == 456,
        channel_exists=lambda channel_id: False,
    )

    by_field = {issue.field: issue for issue in issues}
    assert by_field["admin_role_id"].ok is True
    assert by_field["welcome_channel_id"].ok is False
    assert by_field["timezone"].ok is True
