from __future__ import annotations

from dataclasses import replace

from services import config_validation, guild_config


class DummyRole:
    def __init__(self, role_id: int):
        self.id = role_id


class DummyPermissions:
    def __init__(
        self,
        *,
        view_channel=True,
        send_messages=True,
        embed_links=True,
        manage_roles=False,
    ):
        self.view_channel = view_channel
        self.send_messages = send_messages
        self.embed_links = embed_links
        self.manage_roles = manage_roles


class DummyMember:
    id = 42


class DummyChannel:
    def __init__(self, channel_id: int, permissions: DummyPermissions | None = None):
        self.id = channel_id
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


def make_config() -> guild_config.GuildConfig:
    return guild_config.GuildConfig(
        guild_id=123,
        admin_role_id=10,
        member_role_id=11,
        pending_role_id=12,
        welcome_channel_id=20,
        onboarding_channel_id=21,
        broadcast_channel_id=22,
        admin_log_channel_id=23,
        timezone="UTC",
        created_at="2026-05-20T00:00:00+00:00",
        updated_at="2026-05-20T00:00:00+00:00",
    )


def make_guild() -> DummyGuild:
    return DummyGuild(
        guild_id=123,
        roles=[DummyRole(10), DummyRole(11), DummyRole(12)],
        channels=[
            DummyChannel(20),
            DummyChannel(21),
            DummyChannel(22),
            DummyChannel(23),
        ],
    )


def test_validate_home_guild_accepts_matching_guild():
    result = config_validation.validate_home_guild(
        configured_home_guild_id=123,
        interaction_guild_id=123,
    )

    assert result.ok is True
    assert not result.errors


def test_validate_config_accepts_complete_config():
    result = config_validation.validate_config(
        config=make_config(),
        guild=make_guild(),
        configured_home_guild_id=123,
        bot_user_id=42,
    )

    assert result.ok is True
    assert not result.errors
    assert config_validation.format_checklist_lines(result)


def test_validate_config_reports_missing_role():
    guild = make_guild()
    guild._roles.pop(11)

    result = config_validation.validate_config(
        config=make_config(),
        guild=guild,
        configured_home_guild_id=123,
        bot_user_id=42,
    )

    assert result.ok is False
    assert any(issue.field == "member_role_id" for issue in result.errors)


def test_validate_config_reports_missing_channel():
    guild = make_guild()
    guild._channels.pop(22)

    result = config_validation.validate_config(
        config=make_config(),
        guild=guild,
        configured_home_guild_id=123,
        bot_user_id=42,
    )

    assert result.ok is False
    assert any(issue.field == "broadcast_channel_id" for issue in result.errors)


def test_validate_config_reports_missing_send_permission():
    guild = make_guild()
    guild._channels[20] = DummyChannel(
        20,
        DummyPermissions(send_messages=False),
    )

    result = config_validation.validate_config(
        config=make_config(),
        guild=guild,
        configured_home_guild_id=123,
        bot_user_id=42,
    )

    assert result.ok is False
    assert any(
        issue.field == "welcome_channel_id.send_messages"
        for issue in result.errors
    )


def test_validate_config_treats_manage_roles_as_warning():
    guild = make_guild()

    result = config_validation.validate_config(
        config=make_config(),
        guild=guild,
        configured_home_guild_id=123,
        bot_user_id=42,
    )

    assert result.ok is True
    assert any(
        issue.field == "welcome_channel_id.manage_roles"
        for issue in result.warnings
    )


def test_validate_config_reports_missing_config_row():
    result = config_validation.validate_config(
        config=None,
        guild=make_guild(),
        configured_home_guild_id=123,
        bot_user_id=42,
    )

    assert result.ok is False
    assert any(issue.field == "guild_config" for issue in result.errors)


def test_validate_config_reports_bad_timezone():
    config = replace(make_config(), timezone="Not/AZone")

    result = config_validation.validate_config(
        config=config,
        guild=make_guild(),
        configured_home_guild_id=123,
        bot_user_id=42,
    )

    assert result.ok is False
    assert any(issue.field == "timezone" for issue in result.errors)
