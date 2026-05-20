from __future__ import annotations

from types import SimpleNamespace

import pytest

from cogs.admin import Admin
from services import audit_log, guild_config
from services.database import initialize_database, managed_connection


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, message, *, ephemeral=False):
        self.messages.append((message, ephemeral))


class DummyPermissions:
    def __init__(self, administrator):
        self.administrator = administrator


class DummyUser:
    def __init__(self, *, administrator=True, user_id=9001):
        self.id = user_id
        self.guild_permissions = DummyPermissions(administrator)


class DummyInteraction:
    def __init__(self, *, guild_id=123, administrator=True):
        self.guild_id = guild_id
        self.guild = None
        self.user = DummyUser(administrator=administrator)
        self.response = DummyResponse()


def make_admin(*, home_guild_id=123, database_path=":memory:"):
    bot = SimpleNamespace(
        settings=SimpleNamespace(
            home_guild_id=home_guild_id,
            database_path=str(database_path),
        )
    )
    return Admin(bot)


def test_admin_group_declares_admin_permissions_at_class_level():
    source = (Path("cogs") / "admin.py").read_text(encoding="utf-8")

    assert "@app_commands.guild_only()\n@app_commands.default_permissions(administrator=True)\nclass Admin" in source
    assert source.count("@app_commands.default_permissions(administrator=True)") == 1


@pytest.mark.asyncio
async def test_resolve_guild_id_requires_home_guild_id():
    admin = make_admin(home_guild_id=None)
    interaction = DummyInteraction(guild_id=123)

    resolved = await admin._resolve_guild_id(interaction)

    assert resolved is None
    assert interaction.response.messages
    assert "HOME_GUILD_ID" in interaction.response.messages[0][0]
    assert interaction.response.messages[0][1] is True


@pytest.mark.asyncio
async def test_resolve_guild_id_rejects_wrong_guild():
    admin = make_admin(home_guild_id=123)
    interaction = DummyInteraction(guild_id=999)

    resolved = await admin._resolve_guild_id(interaction)

    assert resolved is None
    assert interaction.response.messages
    assert "home guild" in interaction.response.messages[0][0]
    assert interaction.response.messages[0][1] is True


@pytest.mark.asyncio
async def test_resolve_guild_id_accepts_home_guild():
    admin = make_admin(home_guild_id=123)
    interaction = DummyInteraction(guild_id=123)

    resolved = await admin._resolve_guild_id(interaction)

    assert resolved == 123
    assert interaction.response.messages == []


@pytest.mark.asyncio
async def test_reject_non_admin_blocks_user():
    admin = make_admin()
    interaction = DummyInteraction(administrator=False)

    rejected = await admin._reject_non_admin(interaction)

    assert rejected is True
    assert interaction.response.messages == [("Admins only.", True)]


@pytest.mark.asyncio
async def test_reject_non_admin_allows_admin():
    admin = make_admin()
    interaction = DummyInteraction(administrator=True)

    rejected = await admin._reject_non_admin(interaction)

    assert rejected is False
    assert interaction.response.messages == []


def test_admin_config_audit_writer_records_event(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    admin = make_admin(home_guild_id=123, database_path=database_path)

    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        before = guild_config.get_guild_config(connection, 123)
        after = guild_config.ensure_guild_config(connection, 123)

        admin._record_config_audit(
            connection,
            guild_id=123,
            actor_user_id=9001,
            action="guild_config.set_timezone",
            target="timezone",
            before=before,
            after=after,
        )

        events = audit_log.list_audit_events(connection, 123)

    assert len(events) == 1
    assert events[0].guild_id == 123
    assert events[0].actor_user_id == 9001
    assert events[0].action == "guild_config.set_timezone"
    assert events[0].target == "timezone"
    assert audit_log.deserialize_payload(events[0].after_json)["guild_id"] == 123
