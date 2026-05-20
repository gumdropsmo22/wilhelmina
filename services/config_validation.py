from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from services import guild_config

Severity = Literal["error", "warning", "info"]

ROLE_LABELS: dict[str, str] = {
    "admin_role_id": "Admin role",
    "member_role_id": "Member role",
    "pending_role_id": "Pending role",
}

CHANNEL_LABELS: dict[str, str] = {
    "welcome_channel_id": "Welcome channel",
    "onboarding_channel_id": "Onboarding channel",
    "broadcast_channel_id": "Broadcast channel",
    "admin_log_channel_id": "Admin log channel",
}

CHANNEL_PERMISSION_NAMES: tuple[str, ...] = (
    "view_channel",
    "send_messages",
    "embed_links",
)

OPTIONAL_PERMISSION_NAMES: tuple[str, ...] = ("manage_roles",)


@dataclass(frozen=True)
class ConfigCheck:
    """One readiness check result."""

    name: str
    field: str
    value: int | str | None
    ok: bool
    severity: Severity
    message: str


@dataclass(frozen=True)
class ConfigIssue:
    """One failed readiness issue."""

    field: str
    value: int | str | None
    message: str
    severity: Literal["error", "warning"]


@dataclass(frozen=True)
class ConfigValidationResult:
    """Structured readiness result for Wilhelmina's configured home guild."""

    checks: tuple[ConfigCheck, ...]

    @property
    def issues(self) -> tuple[ConfigIssue, ...]:
        return tuple(
            ConfigIssue(
                field=check.field,
                value=check.value,
                message=check.message,
                severity=check.severity,
            )
            for check in self.checks
            if not check.ok and check.severity in {"error", "warning"}
        )

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def errors(self) -> tuple[ConfigIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ConfigIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")


def _check(
    *,
    name: str,
    field: str,
    value: int | str | None,
    ok: bool,
    message: str,
    severity: Severity = "error",
) -> ConfigCheck:
    return ConfigCheck(
        name=name,
        field=field,
        value=value,
        ok=ok,
        severity="info" if ok else severity,
        message=message,
    )


def _get_role(guild: Any, role_id: int | None) -> Any | None:
    if guild is None or role_id is None:
        return None

    get_role = getattr(guild, "get_role", None)
    if callable(get_role):
        return get_role(role_id)

    roles = getattr(guild, "roles", ())
    return next((role for role in roles if getattr(role, "id", None) == role_id), None)


def _get_channel(guild: Any, channel_id: int | None) -> Any | None:
    if guild is None or channel_id is None:
        return None

    get_channel = getattr(guild, "get_channel", None)
    if callable(get_channel):
        return get_channel(channel_id)

    channels = getattr(guild, "channels", ())
    return next(
        (channel for channel in channels if getattr(channel, "id", None) == channel_id),
        None,
    )


def _get_bot_member(guild: Any, bot_user_id: int | None = None) -> Any | None:
    if guild is None:
        return None

    guild_me = getattr(guild, "me", None)
    if guild_me is not None:
        return guild_me

    if bot_user_id is None:
        return None

    get_member = getattr(guild, "get_member", None)
    if callable(get_member):
        return get_member(bot_user_id)

    return None


def _check_permission(channel: Any, member: Any, permission_name: str) -> bool | None:
    if channel is None or member is None:
        return None

    permissions_for = getattr(channel, "permissions_for", None)
    if not callable(permissions_for):
        return None

    permissions = permissions_for(member)
    value = getattr(permissions, permission_name, None)
    if value is None:
        return None

    return bool(value)


def validate_home_guild(
    *,
    configured_home_guild_id: int | None,
    interaction_guild_id: int | None,
) -> ConfigValidationResult:
    """Validate that an admin interaction belongs to the configured home guild."""

    checks: list[ConfigCheck] = []

    checks.append(
        _check(
            name="Home guild configured",
            field="HOME_GUILD_ID",
            value=configured_home_guild_id,
            ok=configured_home_guild_id is not None,
            message="HOME_GUILD_ID is configured"
            if configured_home_guild_id is not None
            else "HOME_GUILD_ID is not configured",
        )
    )

    checks.append(
        _check(
            name="Interaction guild available",
            field="interaction.guild_id",
            value=interaction_guild_id,
            ok=interaction_guild_id is not None,
            message="command is running inside a guild"
            if interaction_guild_id is not None
            else "command is not running inside a guild",
        )
    )

    if configured_home_guild_id is not None and interaction_guild_id is not None:
        checks.append(
            _check(
                name="Interaction guild matches home guild",
                field="interaction.guild_id",
                value=interaction_guild_id,
                ok=int(configured_home_guild_id) == int(interaction_guild_id),
                message="command is running in the configured home guild"
                if int(configured_home_guild_id) == int(interaction_guild_id)
                else "command is not running in the configured home guild",
            )
        )

    return ConfigValidationResult(tuple(checks))


def validate_config(
    *,
    config: guild_config.GuildConfig | None,
    guild: Any,
    configured_home_guild_id: int | None,
    bot_user_id: int | None = None,
) -> ConfigValidationResult:
    """Validate stored guild configuration against the live guild objects."""

    checks: list[ConfigCheck] = []

    actual_guild_id = getattr(guild, "id", None)
    checks.extend(
        validate_home_guild(
            configured_home_guild_id=configured_home_guild_id,
            interaction_guild_id=actual_guild_id,
        ).checks
    )

    if config is None:
        checks.append(
            _check(
                name="Guild config row",
                field="guild_config",
                value=None,
                ok=False,
                message="no guild_config row has been stored yet",
            )
        )
        return ConfigValidationResult(tuple(checks))

    checks.append(
        _check(
            name="Stored guild ID",
            field="guild_id",
            value=config.guild_id,
            ok=configured_home_guild_id is not None
            and int(config.guild_id) == int(configured_home_guild_id),
            message="stored guild_id matches HOME_GUILD_ID"
            if configured_home_guild_id is not None
            and int(config.guild_id) == int(configured_home_guild_id)
            else "stored guild_id does not match HOME_GUILD_ID",
        )
    )

    for field, label in ROLE_LABELS.items():
        role_id = getattr(config, field)
        role = _get_role(guild, role_id)
        if role_id is None:
            checks.append(
                _check(
                    name=label,
                    field=field,
                    value=role_id,
                    ok=False,
                    message="role is not configured",
                )
            )
        else:
            checks.append(
                _check(
                    name=label,
                    field=field,
                    value=role_id,
                    ok=role is not None,
                    message="role exists" if role is not None else "role was not found",
                )
            )

    bot_member = _get_bot_member(guild, bot_user_id)

    for field, label in CHANNEL_LABELS.items():
        channel_id = getattr(config, field)
        channel = _get_channel(guild, channel_id)
        if channel_id is None:
            checks.append(
                _check(
                    name=label,
                    field=field,
                    value=channel_id,
                    ok=False,
                    message="channel is not configured",
                )
            )
            continue

        checks.append(
            _check(
                name=label,
                field=field,
                value=channel_id,
                ok=channel is not None,
                message="channel exists" if channel is not None else "channel was not found",
            )
        )

        if channel is None:
            continue

        for permission_name in CHANNEL_PERMISSION_NAMES:
            permission_value = _check_permission(channel, bot_member, permission_name)
            checks.append(
                _check(
                    name=f"{label} permission: {permission_name}",
                    field=f"{field}.{permission_name}",
                    value=channel_id,
                    ok=permission_value is True,
                    severity="warning" if permission_value is None else "error",
                    message="permission is allowed"
                    if permission_value is True
                    else (
                        "permission could not be inspected"
                        if permission_value is None
                        else "permission is missing"
                    ),
                )
            )

        for permission_name in OPTIONAL_PERMISSION_NAMES:
            permission_value = _check_permission(channel, bot_member, permission_name)
            checks.append(
                _check(
                    name=f"{label} optional permission: {permission_name}",
                    field=f"{field}.{permission_name}",
                    value=channel_id,
                    ok=permission_value is True,
                    severity="warning",
                    message="permission is allowed"
                    if permission_value is True
                    else (
                        "permission could not be inspected"
                        if permission_value is None
                        else "permission is missing"
                    ),
                )
            )

    try:
        guild_config.validate_timezone(config.timezone)
    except guild_config.InvalidGuildConfigValue as exc:
        checks.append(
            _check(
                name="Timezone",
                field="timezone",
                value=config.timezone,
                ok=False,
                message=str(exc),
            )
        )
    else:
        checks.append(
            _check(
                name="Timezone",
                field="timezone",
                value=config.timezone,
                ok=True,
                message="timezone is valid",
            )
        )

    return ConfigValidationResult(tuple(checks))


def format_check_lines(result: ConfigValidationResult) -> list[str]:
    """Render readiness checks as aligned text lines."""

    lines: list[str] = []
    for check in result.checks:
        marker = "OK" if check.ok else ("!!" if check.severity == "error" else "??")
        value = "unset" if check.value is None else str(check.value)
        lines.append(f"{marker} {check.name:<44} {value:<24} {check.message}")
    return lines


def format_checklist_lines(result: ConfigValidationResult) -> list[str]:
    """Render readiness checks as a compact checklist."""

    lines: list[str] = []
    for check in result.checks:
        marker = "[x]" if check.ok else ("[!]" if check.severity == "error" else "[?]")
        lines.append(f"{marker} {check.name}: {check.message}")
    return lines
