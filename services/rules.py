from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from typing import Any

from services import audit_log
from services.database import utc_now_iso


class RulesError(RuntimeError):
    """Base error for covenant rules operations."""


class RulesNotConfigured(RulesError):
    """Raised when no active rules covenant exists for a guild."""


@dataclass(frozen=True)
class RulesVersion:
    """One stored rules covenant version."""

    id: int
    guild_id: int
    version_tag: str
    title: str
    intro_text: str
    body_text: str
    accept_label: str
    is_active: bool
    published_channel_id: int | None
    published_message_id: int | None
    created_by: int | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RulesAcceptance:
    """A user's acceptance of one rules covenant version."""

    guild_id: int
    user_id: int
    rules_version_id: int
    accepted_via: str
    accepted_at: str


@dataclass(frozen=True)
class AcceptanceResult:
    """Outcome of recording covenant acceptance."""

    acceptance: RulesAcceptance
    already_accepted: bool


@dataclass(frozen=True)
class RulesSummary:
    """Acceptance count summary for a rules covenant."""

    guild_id: int
    rules_version_id: int
    version_tag: str
    accepted_count: int


def _row_to_rules_version(row: sqlite3.Row) -> RulesVersion:
    return RulesVersion(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        version_tag=str(row["version_tag"]),
        title=str(row["title"]),
        intro_text=str(row["intro_text"]),
        body_text=str(row["body_text"]),
        accept_label=str(row["accept_label"]),
        is_active=bool(row["is_active"]),
        published_channel_id=_optional_int(row["published_channel_id"]),
        published_message_id=_optional_int(row["published_message_id"]),
        created_by=_optional_int(row["created_by"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_acceptance(row: sqlite3.Row) -> RulesAcceptance:
    return RulesAcceptance(
        guild_id=int(row["guild_id"]),
        user_id=int(row["user_id"]),
        rules_version_id=int(row["rules_version_id"]),
        accepted_via=str(row["accepted_via"]),
        accepted_at=str(row["accepted_at"]),
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _require_text(value: str, field: str, *, max_len: int | None = None) -> str:
    text = value.strip()
    if not text:
        raise RulesError(f"{field} cannot be empty")
    if max_len is not None and len(text) > max_len:
        raise RulesError(f"{field} cannot exceed {max_len} characters")
    return text


def upsert_rules_version(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    version_tag: str,
    title: str,
    intro_text: str,
    body_text: str,
    accept_label: str,
    actor_user_id: int,
) -> RulesVersion:
    """Create or update a rules covenant version without activating it."""

    timestamp = utc_now_iso()
    version_tag = _require_text(version_tag, "version_tag", max_len=64)
    title = _require_text(title, "title", max_len=120)
    intro_text = _require_text(intro_text, "intro_text", max_len=1000)
    body_text = _require_text(body_text, "body_text", max_len=5000)
    accept_label = _require_text(accept_label, "accept_label", max_len=80)

    connection.execute(
        """
        INSERT INTO rules_versions (
            guild_id,
            version_tag,
            title,
            intro_text,
            body_text,
            accept_label,
            created_by,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, version_tag) DO UPDATE SET
            title = excluded.title,
            intro_text = excluded.intro_text,
            body_text = excluded.body_text,
            accept_label = excluded.accept_label,
            updated_at = excluded.updated_at
        """,
        (
            int(guild_id),
            version_tag,
            title,
            intro_text,
            body_text,
            accept_label,
            int(actor_user_id),
            timestamp,
            timestamp,
        ),
    )
    rules = get_rules_version(connection, guild_id=guild_id, version_tag=version_tag)
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="rules.upsert_version",
        target=version_tag,
        after=asdict(rules),
    )
    return rules


def get_rules_version(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    version_tag: str,
) -> RulesVersion:
    """Return a stored rules covenant version by tag."""

    row = connection.execute(
        """
        SELECT *
        FROM rules_versions
        WHERE guild_id = ? AND version_tag = ?
        """,
        (int(guild_id), version_tag.strip()),
    ).fetchone()
    if row is None:
        raise RulesNotConfigured("No rules version exists with that tag")
    return _row_to_rules_version(row)


def get_rules_version_by_id(
    connection: sqlite3.Connection,
    rules_version_id: int,
) -> RulesVersion:
    """Return a stored rules covenant version by ID."""

    row = connection.execute(
        "SELECT * FROM rules_versions WHERE id = ?",
        (int(rules_version_id),),
    ).fetchone()
    if row is None:
        raise RulesNotConfigured("No rules version exists with that ID")
    return _row_to_rules_version(row)


def activate_rules_version(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    version_tag: str,
    actor_user_id: int,
) -> RulesVersion:
    """Activate one rules covenant version for a guild."""

    rules = get_rules_version(connection, guild_id=guild_id, version_tag=version_tag)
    timestamp = utc_now_iso()
    before = get_active_rules(connection, guild_id=guild_id, required=False)
    connection.execute(
        """
        UPDATE rules_versions
        SET is_active = 0,
            updated_at = ?
        WHERE guild_id = ? AND is_active = 1
        """,
        (timestamp, int(guild_id)),
    )
    connection.execute(
        """
        UPDATE rules_versions
        SET is_active = 1,
            updated_at = ?
        WHERE id = ?
        """,
        (timestamp, rules.id),
    )
    after = get_rules_version_by_id(connection, rules.id)
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="rules.activate_version",
        target=version_tag,
        before=asdict(before) if before else None,
        after=asdict(after),
    )
    return after


def get_active_rules(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    required: bool = True,
) -> RulesVersion | None:
    """Return the active rules covenant version for a guild."""

    row = connection.execute(
        """
        SELECT *
        FROM rules_versions
        WHERE guild_id = ? AND is_active = 1
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (int(guild_id),),
    ).fetchone()
    if row is None:
        if required:
            raise RulesNotConfigured("No active rules covenant has been configured")
        return None
    return _row_to_rules_version(row)


def list_rules_versions(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    limit: int = 25,
) -> list[RulesVersion]:
    """Return recent rules covenant versions."""

    bounded_limit = max(1, min(int(limit), 100))
    rows = connection.execute(
        """
        SELECT *
        FROM rules_versions
        WHERE guild_id = ?
        ORDER BY is_active DESC, updated_at DESC, id DESC
        LIMIT ?
        """,
        (int(guild_id), bounded_limit),
    ).fetchall()
    return [_row_to_rules_version(row) for row in rows]


def accept_active_rules(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    accepted_via: str,
    actor_user_id: int | None = None,
) -> AcceptanceResult:
    """Record acceptance for the active rules covenant."""

    rules = get_active_rules(connection, guild_id=guild_id)
    if rules is None:
        raise RulesNotConfigured("No active rules covenant has been configured")
    return accept_rules_version(
        connection,
        guild_id=guild_id,
        user_id=user_id,
        rules_version_id=rules.id,
        accepted_via=accepted_via,
        actor_user_id=actor_user_id,
    )


def accept_rules_version(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    rules_version_id: int,
    accepted_via: str,
    actor_user_id: int | None = None,
) -> AcceptanceResult:
    """Record acceptance of one rules covenant version idempotently."""

    accepted_via = _require_text(accepted_via, "accepted_via", max_len=32)
    existing = connection.execute(
        """
        SELECT *
        FROM rules_acceptance
        WHERE guild_id = ? AND user_id = ? AND rules_version_id = ?
        """,
        (int(guild_id), int(user_id), int(rules_version_id)),
    ).fetchone()
    already_accepted = existing is not None

    if already_accepted:
        acceptance = _row_to_acceptance(existing)
    else:
        timestamp = utc_now_iso()
        connection.execute(
            """
            INSERT INTO rules_acceptance (
                guild_id,
                user_id,
                rules_version_id,
                accepted_via,
                accepted_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(guild_id), int(user_id), int(rules_version_id), accepted_via, timestamp),
        )
        row = connection.execute(
            """
            SELECT *
            FROM rules_acceptance
            WHERE guild_id = ? AND user_id = ? AND rules_version_id = ?
            """,
            (int(guild_id), int(user_id), int(rules_version_id)),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to record rules acceptance")
        acceptance = _row_to_acceptance(row)

    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id or user_id,
        action="rules.accept",
        target=str(user_id),
        before=None,
        after={
            "rules_version_id": int(rules_version_id),
            "already_accepted": already_accepted,
            "accepted_via": accepted_via,
        },
    )
    return AcceptanceResult(acceptance=acceptance, already_accepted=already_accepted)


def get_acceptance_for_user(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    rules_version_id: int | None = None,
) -> RulesAcceptance | None:
    """Return a user's acceptance for a specific or active rules version."""

    target_version_id = rules_version_id
    if target_version_id is None:
        active = get_active_rules(connection, guild_id=guild_id, required=False)
        if active is None:
            return None
        target_version_id = active.id

    row = connection.execute(
        """
        SELECT *
        FROM rules_acceptance
        WHERE guild_id = ? AND user_id = ? AND rules_version_id = ?
        """,
        (int(guild_id), int(user_id), int(target_version_id)),
    ).fetchone()
    if row is None:
        return None
    return _row_to_acceptance(row)


def update_published_message(
    connection: sqlite3.Connection,
    *,
    rules_version_id: int,
    channel_id: int,
    message_id: int,
    actor_user_id: int,
) -> RulesVersion:
    """Store the currently published Covenant Gate message."""

    before = get_rules_version_by_id(connection, rules_version_id)
    timestamp = utc_now_iso()
    connection.execute(
        """
        UPDATE rules_versions
        SET published_channel_id = ?,
            published_message_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (int(channel_id), int(message_id), timestamp, int(rules_version_id)),
    )
    after = get_rules_version_by_id(connection, rules_version_id)
    audit_log.record_audit_event(
        connection,
        guild_id=after.guild_id,
        actor_user_id=actor_user_id,
        action="rules.publish",
        target=str(rules_version_id),
        before=asdict(before),
        after=asdict(after),
    )
    return after


def summarize_acceptance(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
) -> RulesSummary:
    """Return acceptance count for the active rules covenant."""

    active = get_active_rules(connection, guild_id=guild_id)
    if active is None:
        raise RulesNotConfigured("No active rules covenant has been configured")
    row = connection.execute(
        """
        SELECT COUNT(*) AS accepted_count
        FROM rules_acceptance
        WHERE guild_id = ? AND rules_version_id = ?
        """,
        (int(guild_id), active.id),
    ).fetchone()
    return RulesSummary(
        guild_id=int(guild_id),
        rules_version_id=active.id,
        version_tag=active.version_tag,
        accepted_count=int(row["accepted_count"] if row else 0),
    )
