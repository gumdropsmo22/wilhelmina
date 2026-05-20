from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.database import utc_now_iso

DEFAULT_TIMEZONE = "UTC"

ROLE_FIELDS = frozenset({"admin_role_id", "member_role_id", "pending_role_id"})
CHANNEL_FIELDS = frozenset(
    {
        "welcome_channel_id",
        "onboarding_channel_id",
        "broadcast_channel_id",
        "admin_log_channel_id",
    }
)
NULLABLE_CONFIG_FIELDS = ROLE_FIELDS | CHANNEL_FIELDS
CLEARABLE_CONFIG_FIELDS = NULLABLE_CONFIG_FIELDS | {"timezone"}


class GuildConfigError(ValueError):
    """Base exception for invalid guild configuration changes."""


class InvalidGuildConfigField(GuildConfigError):
    """Raised when a config command targets an unknown field."""


class InvalidGuildConfigValue(GuildConfigError):
    """Raised when a config command supplies an invalid value."""


@dataclass(frozen=True)
class GuildConfig:
    guild_id: int
    admin_role_id: int | None
    member_role_id: int | None
    pending_role_id: int | None
    welcome_channel_id: int | None
    onboarding_channel_id: int | None
    broadcast_channel_id: int | None
    admin_log_channel_id: int | None
    timezone: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    value: int | str | None
    ok: bool
    message: str


def validate_snowflake(value: int | str, field_name: str) -> int:
    """Validate a Discord snowflake-style positive integer."""

    try:
        snowflake = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidGuildConfigValue(f"{field_name} must be an integer ID.") from exc

    if snowflake <= 0:
        raise InvalidGuildConfigValue(f"{field_name} must be a positive integer ID.")

    return snowflake


def validate_timezone(timezone_name: str) -> str:
    """Validate an IANA timezone name and return the stripped value."""

    timezone = (timezone_name or "").strip()
    if not timezone:
        raise InvalidGuildConfigValue("timezone must not be empty")

    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise InvalidGuildConfigValue(f"Unknown IANA timezone: {timezone!r}") from exc

    return timezone


def _validate_field(field: str, allowed_fields: frozenset[str], field_kind: str) -> str:
    if field not in allowed_fields:
        allowed = ", ".join(sorted(allowed_fields))
        raise InvalidGuildConfigField(
            f"Unknown {field_kind} field {field!r}. Allowed fields: {allowed}"
        )
    return field


def _validate_guild_id(guild_id: int | str) -> int:
    return validate_snowflake(guild_id, "guild_id")


def _row_to_config(row: sqlite3.Row | None) -> GuildConfig | None:
    if row is None:
        return None

    return GuildConfig(
        guild_id=int(row["guild_id"]),
        admin_role_id=row["admin_role_id"],
        member_role_id=row["member_role_id"],
        pending_role_id=row["pending_role_id"],
        welcome_channel_id=row["welcome_channel_id"],
        onboarding_channel_id=row["onboarding_channel_id"],
        broadcast_channel_id=row["broadcast_channel_id"],
        admin_log_channel_id=row["admin_log_channel_id"],
        timezone=str(row["timezone"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def config_to_dict(config: GuildConfig) -> dict[str, Any]:
    """Serialize a guild config for display or audit snapshots."""

    return asdict(config)


def config_to_audit_dict(config: GuildConfig | None) -> dict[str, Any] | None:
    """Serialize a nullable guild config for audit snapshots."""

    if config is None:
        return None
    return config_to_dict(config)


def get_guild_config(connection: sqlite3.Connection, guild_id: int | str) -> GuildConfig | None:
    """Fetch one guild config row."""

    normalized_guild_id = _validate_guild_id(guild_id)
    row = connection.execute(
        "SELECT * FROM guild_config WHERE guild_id = ?",
        (normalized_guild_id,),
    ).fetchone()
    return _row_to_config(row)


def ensure_guild_config(
    connection: sqlite3.Connection,
    guild_id: int | str,
    *,
    timezone: str = DEFAULT_TIMEZONE,
) -> GuildConfig:
    """Create a guild config row if missing, then return it."""

    normalized_guild_id = _validate_guild_id(guild_id)
    normalized_timezone = validate_timezone(timezone)
    existing = get_guild_config(connection, normalized_guild_id)
    if existing is not None:
        return existing

    now = utc_now_iso()
    connection.execute(
        """
        INSERT INTO guild_config (
            guild_id,
            timezone,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (normalized_guild_id, normalized_timezone, now, now),
    )

    created = get_guild_config(connection, normalized_guild_id)
    if created is None:
        raise RuntimeError("Failed to create guild_config row")
    return created


def _update_config_fields(
    connection: sqlite3.Connection,
    guild_id: int | str,
    changes: dict[str, int | str | None],
) -> tuple[GuildConfig | None, GuildConfig]:
    normalized_guild_id = _validate_guild_id(guild_id)
    if not changes:
        after = ensure_guild_config(connection, normalized_guild_id)
        return after, after

    before = get_guild_config(connection, normalized_guild_id)
    ensure_guild_config(connection, normalized_guild_id)

    updated_at = utc_now_iso()
    assignments = ", ".join([f"{field} = ?" for field in changes])
    values = list(changes.values())
    values.extend([updated_at, normalized_guild_id])

    connection.execute(
        f"""
        UPDATE guild_config
        SET {assignments}, updated_at = ?
        WHERE guild_id = ?
        """,
        values,
    )

    after = get_guild_config(connection, normalized_guild_id)
    if after is None:
        raise RuntimeError("Failed to update guild_config row")
    return before, after


def set_role(
    connection: sqlite3.Connection,
    guild_id: int | str,
    field: str,
    role_id: int | str,
) -> tuple[GuildConfig | None, GuildConfig]:
    """Set a configured Discord role ID."""

    normalized_field = _validate_field(field, ROLE_FIELDS, "role")
    normalized_role_id = validate_snowflake(role_id, normalized_field)
    return _update_config_fields(connection, guild_id, {normalized_field: normalized_role_id})


def set_channel(
    connection: sqlite3.Connection,
    guild_id: int | str,
    field: str,
    channel_id: int | str,
) -> tuple[GuildConfig | None, GuildConfig]:
    """Set a configured Discord channel ID."""

    normalized_field = _validate_field(field, CHANNEL_FIELDS, "channel")
    normalized_channel_id = validate_snowflake(channel_id, normalized_field)
    return _update_config_fields(connection, guild_id, {normalized_field: normalized_channel_id})


def set_timezone(
    connection: sqlite3.Connection,
    guild_id: int | str,
    timezone_name: str,
) -> tuple[GuildConfig | None, GuildConfig]:
    """Set the guild's configured IANA timezone."""

    normalized_timezone = validate_timezone(timezone_name)
    return _update_config_fields(connection, guild_id, {"timezone": normalized_timezone})


def clear_guild_config(
    connection: sqlite3.Connection,
    guild_id: int | str,
    fields: Iterable[str] | None = None,
) -> tuple[GuildConfig | None, GuildConfig | None]:
    """Clear selected guild config fields, or delete the row when fields is None."""

    normalized_guild_id = _validate_guild_id(guild_id)
    before = get_guild_config(connection, normalized_guild_id)

    if fields is None:
        if before is not None:
            connection.execute(
                "DELETE FROM guild_config WHERE guild_id = ?",
                (normalized_guild_id,),
            )
        return before, None

    normalized_fields = list(dict.fromkeys(fields))
    if not normalized_fields:
        raise InvalidGuildConfigField("At least one field must be provided for partial clear.")

    for field in normalized_fields:
        _validate_field(field, CLEARABLE_CONFIG_FIELDS, "clearable")

    if before is None:
        return None, None

    changes: dict[str, int | str | None] = {}
    for field in normalized_fields:
        changes[field] = DEFAULT_TIMEZONE if field == "timezone" else None

    _, after = _update_config_fields(connection, normalized_guild_id, changes)
    return before, after


def validate_guild_config(
    config: GuildConfig,
    *,
    role_exists: Callable[[int], bool] | None = None,
    channel_exists: Callable[[int], bool] | None = None,
) -> list[ValidationIssue]:
    """Validate config completeness and optional Discord object existence."""

    issues: list[ValidationIssue] = []

    for field in sorted(ROLE_FIELDS):
        value = getattr(config, field)
        if value is None:
            issues.append(ValidationIssue(field, value, False, "unset"))
        elif role_exists is not None and not role_exists(value):
            issues.append(ValidationIssue(field, value, False, "role not found in guild"))
        else:
            issues.append(ValidationIssue(field, value, True, "ok"))

    for field in sorted(CHANNEL_FIELDS):
        value = getattr(config, field)
        if value is None:
            issues.append(ValidationIssue(field, value, False, "unset"))
        elif channel_exists is not None and not channel_exists(value):
            issues.append(ValidationIssue(field, value, False, "channel not found in guild"))
        else:
            issues.append(ValidationIssue(field, value, True, "ok"))

    try:
        validate_timezone(config.timezone)
    except InvalidGuildConfigValue as exc:
        issues.append(ValidationIssue("timezone", config.timezone, False, str(exc)))
    else:
        issues.append(ValidationIssue("timezone", config.timezone, True, "ok"))

    return issues
