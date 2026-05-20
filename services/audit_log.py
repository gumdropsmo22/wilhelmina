from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from services.database import utc_now_iso


@dataclass(frozen=True)
class AuditEvent:
    id: int
    guild_id: int
    actor_user_id: int
    action: str
    target: str
    before_json: str | None
    after_json: str | None
    created_at: str


def _json_payload(payload: Any) -> str | None:
    if payload is None:
        return None

    if is_dataclass(payload) and not isinstance(payload, type):
        payload = asdict(payload)

    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _row_to_event(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        actor_user_id=int(row["actor_user_id"]),
        action=str(row["action"]),
        target=str(row["target"]),
        before_json=row["before_json"],
        after_json=row["after_json"],
        created_at=str(row["created_at"]),
    )


def deserialize_payload(value: str | None) -> Any:
    """Deserialize a stored audit snapshot."""

    if value is None:
        return None
    return json.loads(value)


def record_audit_event(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    actor_user_id: int,
    action: str,
    target: str,
    before: Any = None,
    after: Any = None,
    created_at: str | None = None,
) -> AuditEvent:
    """Insert and return one audit log event."""

    timestamp = created_at or utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO audit_log (
            guild_id,
            actor_user_id,
            action,
            target,
            before_json,
            after_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(guild_id),
            int(actor_user_id),
            action.strip(),
            target.strip(),
            _json_payload(before),
            _json_payload(after),
            timestamp,
        ),
    )

    event_id = int(cursor.lastrowid)
    row = connection.execute("SELECT * FROM audit_log WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise RuntimeError("Failed to create audit event")

    return _row_to_event(row)


def list_audit_events(
    connection: sqlite3.Connection,
    guild_id: int,
    *,
    limit: int = 10,
) -> list[AuditEvent]:
    """Return recent audit events for one guild."""

    bounded_limit = max(1, min(int(limit), 100))
    rows = connection.execute(
        """
        SELECT *
        FROM audit_log
        WHERE guild_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (int(guild_id), bounded_limit),
    ).fetchall()

    return [_row_to_event(row) for row in rows]
