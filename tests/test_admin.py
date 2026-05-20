from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cogs.admin import Admin, _format_audit_event, _format_readiness_block
from services import audit_log, config_validation, guild_config
from services.database import initialize_database, managed_connection


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, message, *, ephemeral=False):
        self.messages.append((message, ephemeral))


class DummyPermissions:
    def __init__(
        self,
        administrator=True,
        *,
        view_channel=True,
        send_messages=True,
        embed_links=True,
        manage_roles=False,
    ):
        self.administrator = administrator
        self.view_channel = view_channel
        self.send_messages = send_messages
        self.embed_links = embed_links
        self.manage_roles = manage_roles


class DummyUser:
    def __init__(self, *, administrator=True, user_id=9001):
        self.id = user_id
        self.guild_permissions = DummyPermissions(administrator)


class DummyRole:
    def __init__(self, role_id: int, name: str):
        self.id = role_id
        self.name = name


class DummyMember:
    id = 4242


class DummyChannel:
    def __init__(self, channel_id: int, name: str, permissions=None):
        self.id = channel_id
        self.name = name
        self._permissions = permissions or DummyPermissions()

    def permissions_for(self, member):
        return self._permissions


class DummyGuild:
    def __init__(self, *, guild_id=123, roles=(), channels=(), me=None):
        self.id = guild_id
        self._roles = {role.id: role for role in roles}
        self._channels = {channel.id: channel for channel in channels}
        self.me = me or DummyMember()

    def get_role(self, role_id: int):
        return self._roles.get(role_id)

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)

    def get_member(self, member_id: int):
        if member_id == self.me.id:
            return self.me
        return None


class DummyInteraction:
    def __init__(self, *, guild_id=123, administrator=True, guild=None):
        self.guild_id = guild_id
        self.guild = guild
        self.user = DummyUser(administrator=administrator)
        self.response = DummyResponse()


def make_admin(*, home_guild_id=123, database_path=":memory:"):
    bot = SimpleNamespace(
        settings=SimpleNamespace(
            home_guild_id=home_guild_id,
            database_path=str(database_path),
        ),
        user=SimpleNamespace(id=4242),
    )
    return Admin(bot)


def make_guild() -> DummyGuild:
    return DummyGuild(
        guild_id=123,
        roles=[
            DummyRole(10, "admin"),
            DummyRole(11, "member"),
            DummyRole(12, "pending"),
        ],
        channels=[
            DummyChannel(20, "welcome"),
            DummyChannel(21, "onboarding"),
            DummyChannel(22, "broadcast"),
            DummyChannel(23, "admin-log"),
        ],
    )


def seed_complete_config(database_path):
    initialize_database(database_path)
    with managed_connection(database_path) as connection:
        guild_config.set_role(connection, 123, "admin_role_id", 10)
        guild_config.set_role(connection, 123, "member_role_id", 11)
        guild_config.set_role(connection, 123, "pending_role_id", 12)
        guild_config.set_channel(connection, 123, "welcome_channel_id", 20)
        guild_config.set_channel(connection, 123, "onboarding_channel_id", 21)
        guild_config.set_channel(connection, 123, "broadcast_channel_id", 22)
        guild_config.set_channel(connection, 123, "admin_log_channel_id", 23)


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


@pytest.mark.asyncio
async def test_guard_admin_home_guild_combines_admin_and_guild_checks():
    admin = make_admin(home_guild_id=123)
    interaction = DummyInteraction(guild_id=999, administrator=True)

    resolved = await admin._guard_admin_home_guild(interaction)

    assert resolved is None
    assert "home guild" in interaction.response.messages[0][0]


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


def test_build_readiness_result_uses_stored_config_and_guild_objects(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    seed_complete_config(database_path)
    admin = make_admin(home_guild_id=123, database_path=database_path)
    interaction = DummyInteraction(guild_id=123, guild=make_guild())

    result = admin._build_readiness_result(interaction, 123)

    assert result.ok is True
    assert any(check.field == "admin_role_id" for check in result.checks)
    assert any(check.field == "welcome_channel_id.send_messages" for check in result.checks)


def test_readiness_block_formats_status_and_checklist():
    result = config_validation.ConfigValidationResult(
        (
            config_validation.ConfigCheck(
                name="Example",
                field="example",
                value=None,
                ok=False,
                severity="error",
                message="missing",
            ),
        )
    )

    status = _format_readiness_block("Status", result)
    checklist = _format_readiness_block("Checklist", result, checklist=True)

    assert "overall_ok = false" in status
    assert "[!] Example: missing" in checklist


def test_format_audit_event_is_compact():
    event = audit_log.AuditEvent(
        id=1,
        guild_id=123,
        actor_user_id=9001,
        action="guild_config.set_role",
        target="admin_role_id",
        before_json=None,
        after_json=None,
        created_at="2026-05-20T00:00:00+00:00",
    )

    assert _format_audit_event(event) == (
        "#1 2026-05-20T00:00:00+00:00 "
        "actor=9001 action=guild_config.set_role target=admin_role_id"
    )
