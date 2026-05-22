from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from typing import Literal

from services import audit_log
from services.database import utc_now_iso
from services.guild_config import validate_snowflake

OnboardingStateValue = Literal["pending", "approved", "rejected", "completed"]

PENDING: OnboardingStateValue = "pending"
APPROVED: OnboardingStateValue = "approved"
REJECTED: OnboardingStateValue = "rejected"
COMPLETED: OnboardingStateValue = "completed"

VALID_STATES: frozenset[str] = frozenset({PENDING, APPROVED, REJECTED, COMPLETED})
TERMINAL_STATES: frozenset[str] = frozenset({REJECTED, COMPLETED})
MAX_NOTES_LENGTH = 1000


class OnboardingError(ValueError):
    """Base exception for invalid onboarding operations."""


class InvalidOnboardingState(OnboardingError):
    """Raised when an unknown onboarding state is requested."""


class InvalidOnboardingTransition(OnboardingError):
    """Raised when a state transition is not allowed."""


@dataclass(frozen=True)
class OnboardingRecord:
    guild_id: int
    user_id: int
    state: OnboardingStateValue
    started_at: str
    completed_at: str | None
    approved_by: int | None
    rejected_by: int | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class OnboardingSummary:
    guild_id: int
    total: int
    pending: int
    approved: int
    rejected: int
    completed: int


def _validate_state(state: str) -> OnboardingStateValue:
    normalized = (state or "").strip().lower()
    if normalized not in VALID_STATES:
        allowed = ", ".join(sorted(VALID_STATES))
        raise InvalidOnboardingState(f"Unknown onboarding state {state!r}. Allowed: {allowed}")
    return normalized  # type: ignore[return-value]


def _validate_notes(notes: str | None) -> str | None:
    if notes is None:
        return None

    normalized = notes.strip()
    if not normalized:
        return None

    if len(normalized) > MAX_NOTES_LENGTH:
        raise OnboardingError(f"notes must be {MAX_NOTES_LENGTH} characters or fewer")

    return normalized


def _row_to_record(row: sqlite3.Row | None) -> OnboardingRecord | None:
    if row is None:
        return None

    return OnboardingRecord(
        guild_id=int(row["guild_id"]),
        user_id=int(row["user_id"]),
        state=_validate_state(str(row["state"])),
        started_at=str(row["started_at"]),
        completed_at=row["completed_at"],
        approved_by=row["approved_by"],
        rejected_by=row["rejected_by"],
        notes=row["notes"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def record_to_dict(record: OnboardingRecord) -> dict[str, int | str | None]:
    """Serialize an onboarding record for display or audit snapshots."""

    return asdict(record)


def record_to_audit_dict(record: OnboardingRecord | None) -> dict[str, int | str | None] | None:
    """Serialize a nullable onboarding record for audit snapshots."""

    if record is None:
        return None
    return record_to_dict(record)


def _record_audit(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    actor_user_id: int | None,
    action: str,
    target_user_id: int,
    before: OnboardingRecord | None,
    after: OnboardingRecord | None,
) -> None:
    if actor_user_id is None:
        return

    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action=action,
        target=str(target_user_id),
        before=record_to_audit_dict(before),
        after=record_to_audit_dict(after),
    )


def get_onboarding_record(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
) -> OnboardingRecord | None:
    """Fetch one onboarding record by guild and user."""

    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    normalized_user_id = validate_snowflake(user_id, "user_id")
    row = connection.execute(
        """
        SELECT *
        FROM onboarding_state
        WHERE guild_id = ? AND user_id = ?
        """,
        (normalized_guild_id, normalized_user_id),
    ).fetchone()
    return _row_to_record(row)


def list_onboarding_records(
    connection: sqlite3.Connection,
    guild_id: int | str,
    *,
    state: str | None = None,
    limit: int = 25,
) -> list[OnboardingRecord]:
    """List recent onboarding records for a guild, optionally filtered by state."""

    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    bounded_limit = max(1, min(int(limit), 100))

    if state is None:
        rows = connection.execute(
            """
            SELECT *
            FROM onboarding_state
            WHERE guild_id = ?
            ORDER BY updated_at DESC, user_id ASC
            LIMIT ?
            """,
            (normalized_guild_id, bounded_limit),
        ).fetchall()
    else:
        normalized_state = _validate_state(state)
        rows = connection.execute(
            """
            SELECT *
            FROM onboarding_state
            WHERE guild_id = ? AND state = ?
            ORDER BY updated_at DESC, user_id ASC
            LIMIT ?
            """,
            (normalized_guild_id, normalized_state, bounded_limit),
        ).fetchall()

    return [_row_to_record(row) for row in rows if row is not None]


def summarize_onboarding(
    connection: sqlite3.Connection,
    guild_id: int | str,
) -> OnboardingSummary:
    """Count onboarding records by state for one guild."""

    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    counts = {state: 0 for state in VALID_STATES}
    rows = connection.execute(
        """
        SELECT state, COUNT(*) AS count
        FROM onboarding_state
        WHERE guild_id = ?
        GROUP BY state
        """,
        (normalized_guild_id,),
    ).fetchall()

    for row in rows:
        state = _validate_state(str(row["state"]))
        counts[state] = int(row["count"])

    return OnboardingSummary(
        guild_id=normalized_guild_id,
        total=sum(counts.values()),
        pending=counts[PENDING],
        approved=counts[APPROVED],
        rejected=counts[REJECTED],
        completed=counts[COMPLETED],
    )


def list_onboarding_history(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    limit: int = 10,
) -> list[audit_log.AuditEvent]:
    """Return recent audit events for one user's onboarding record."""

    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    normalized_user_id = validate_snowflake(user_id, "user_id")
    return audit_log.list_audit_events_for_target(
        connection,
        normalized_guild_id,
        normalized_user_id,
        limit=limit,
    )


def _apply_state_fields(
    *,
    state: OnboardingStateValue,
    actor_user_id: int | None,
    notes: str | None,
    now: str,
) -> dict[str, int | str | None]:
    fields: dict[str, int | str | None] = {
        "state": state,
        "updated_at": now,
        "notes": _validate_notes(notes),
    }

    if state == PENDING:
        fields.update(
            {
                "completed_at": None,
                "approved_by": None,
                "rejected_by": None,
            }
        )
    elif state == APPROVED:
        fields.update(
            {
                "completed_at": None,
                "approved_by": actor_user_id,
                "rejected_by": None,
            }
        )
    elif state == REJECTED:
        fields.update(
            {
                "completed_at": None,
                "approved_by": None,
                "rejected_by": actor_user_id,
            }
        )
    elif state == COMPLETED:
        fields.update(
            {
                "completed_at": now,
                "rejected_by": None,
            }
        )

    return fields


def _update_existing_record(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    fields: dict[str, int | str | None],
) -> OnboardingRecord:
    assignments = ", ".join([f"{field} = ?" for field in fields])
    values = list(fields.values())
    values.extend([guild_id, user_id])
    connection.execute(
        f"""
        UPDATE onboarding_state
        SET {assignments}
        WHERE guild_id = ? AND user_id = ?
        """,
        values,
    )

    updated = get_onboarding_record(connection, guild_id, user_id)
    if updated is None:
        raise RuntimeError("Failed to update onboarding_state row")
    return updated


def start_onboarding(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    actor_user_id: int | str | None = None,
    notes: str | None = None,
) -> tuple[OnboardingRecord | None, OnboardingRecord]:
    """Create or reset a user to pending onboarding."""

    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    normalized_user_id = validate_snowflake(user_id, "user_id")
    normalized_actor_id = (
        validate_snowflake(actor_user_id, "actor_user_id")
        if actor_user_id is not None
        else None
    )
    normalized_notes = _validate_notes(notes)
    before = get_onboarding_record(connection, normalized_guild_id, normalized_user_id)
    now = utc_now_iso()

    if before is None:
        connection.execute(
            """
            INSERT INTO onboarding_state (
                guild_id,
                user_id,
                state,
                started_at,
                completed_at,
                approved_by,
                rejected_by,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?)
            """,
            (
                normalized_guild_id,
                normalized_user_id,
                PENDING,
                now,
                normalized_notes,
                now,
                now,
            ),
        )
    else:
        fields = _apply_state_fields(
            state=PENDING,
            actor_user_id=normalized_actor_id,
            notes=normalized_notes,
            now=now,
        )
        fields["started_at"] = now
        _update_existing_record(
            connection,
            guild_id=normalized_guild_id,
            user_id=normalized_user_id,
            fields=fields,
        )

    after = get_onboarding_record(connection, normalized_guild_id, normalized_user_id)
    if after is None:
        raise RuntimeError("Failed to create onboarding_state row")

    _record_audit(
        connection,
        guild_id=normalized_guild_id,
        actor_user_id=normalized_actor_id,
        action="onboarding.start",
        target_user_id=normalized_user_id,
        before=before,
        after=after,
    )
    return before, after


def update_notes(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    actor_user_id: int | str,
    notes: str | None,
) -> tuple[OnboardingRecord, OnboardingRecord]:
    """Update admin notes for an existing onboarding record without changing state."""

    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    normalized_user_id = validate_snowflake(user_id, "user_id")
    normalized_actor_id = validate_snowflake(actor_user_id, "actor_user_id")
    before = get_onboarding_record(connection, normalized_guild_id, normalized_user_id)
    if before is None:
        raise InvalidOnboardingTransition("onboarding has not been started for this user")

    after = _update_existing_record(
        connection,
        guild_id=normalized_guild_id,
        user_id=normalized_user_id,
        fields={"notes": _validate_notes(notes), "updated_at": utc_now_iso()},
    )
    _record_audit(
        connection,
        guild_id=normalized_guild_id,
        actor_user_id=normalized_actor_id,
        action="onboarding.update_notes",
        target_user_id=normalized_user_id,
        before=before,
        after=after,
    )
    return before, after


def _transition(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    new_state: OnboardingStateValue,
    actor_user_id: int | str | None,
    notes: str | None,
    action: str,
) -> tuple[OnboardingRecord, OnboardingRecord]:
    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    normalized_user_id = validate_snowflake(user_id, "user_id")
    normalized_actor_id = (
        validate_snowflake(actor_user_id, "actor_user_id")
        if actor_user_id is not None
        else None
    )

    before = get_onboarding_record(connection, normalized_guild_id, normalized_user_id)
    if before is None:
        raise InvalidOnboardingTransition("onboarding has not been started for this user")

    if before.state in TERMINAL_STATES and before.state != new_state:
        raise InvalidOnboardingTransition(
            f"cannot transition from terminal state {before.state!r}; use override_state"
        )

    if new_state == COMPLETED and before.state != APPROVED:
        raise InvalidOnboardingTransition("only approved onboarding can be completed")

    now = utc_now_iso()
    fields = _apply_state_fields(
        state=new_state,
        actor_user_id=normalized_actor_id,
        notes=notes if notes is not None else before.notes,
        now=now,
    )
    if new_state == COMPLETED and before.approved_by is not None:
        fields["approved_by"] = before.approved_by

    after = _update_existing_record(
        connection,
        guild_id=normalized_guild_id,
        user_id=normalized_user_id,
        fields=fields,
    )
    _record_audit(
        connection,
        guild_id=normalized_guild_id,
        actor_user_id=normalized_actor_id,
        action=action,
        target_user_id=normalized_user_id,
        before=before,
        after=after,
    )
    return before, after


def approve_onboarding(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    actor_user_id: int | str,
    notes: str | None = None,
) -> tuple[OnboardingRecord, OnboardingRecord]:
    """Mark a pending onboarding record as approved."""

    return _transition(
        connection,
        guild_id,
        user_id,
        new_state=APPROVED,
        actor_user_id=actor_user_id,
        notes=notes,
        action="onboarding.approve",
    )


def reject_onboarding(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    actor_user_id: int | str,
    notes: str | None = None,
) -> tuple[OnboardingRecord, OnboardingRecord]:
    """Mark an onboarding record as rejected."""

    return _transition(
        connection,
        guild_id,
        user_id,
        new_state=REJECTED,
        actor_user_id=actor_user_id,
        notes=notes,
        action="onboarding.reject",
    )


def complete_onboarding(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    actor_user_id: int | str,
    notes: str | None = None,
) -> tuple[OnboardingRecord, OnboardingRecord]:
    """Mark an approved onboarding record as completed."""

    return _transition(
        connection,
        guild_id,
        user_id,
        new_state=COMPLETED,
        actor_user_id=actor_user_id,
        notes=notes,
        action="onboarding.complete",
    )


def override_state(
    connection: sqlite3.Connection,
    guild_id: int | str,
    user_id: int | str,
    *,
    state: str,
    actor_user_id: int | str,
    notes: str | None = None,
) -> tuple[OnboardingRecord | None, OnboardingRecord]:
    """Force-set a user's onboarding state for manual admin correction."""

    normalized_guild_id = validate_snowflake(guild_id, "guild_id")
    normalized_user_id = validate_snowflake(user_id, "user_id")
    normalized_actor_id = validate_snowflake(actor_user_id, "actor_user_id")
    normalized_state = _validate_state(state)
    before = get_onboarding_record(connection, normalized_guild_id, normalized_user_id)
    now = utc_now_iso()
    fields = _apply_state_fields(
        state=normalized_state,
        actor_user_id=normalized_actor_id,
        notes=notes,
        now=now,
    )

    if before is None:
        connection.execute(
            """
            INSERT INTO onboarding_state (
                guild_id,
                user_id,
                state,
                started_at,
                completed_at,
                approved_by,
                rejected_by,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_guild_id,
                normalized_user_id,
                fields["state"],
                now,
                fields.get("completed_at"),
                fields.get("approved_by"),
                fields.get("rejected_by"),
                fields.get("notes"),
                now,
                now,
            ),
        )
    else:
        _update_existing_record(
            connection,
            guild_id=normalized_guild_id,
            user_id=normalized_user_id,
            fields=fields,
        )

    after = get_onboarding_record(connection, normalized_guild_id, normalized_user_id)
    if after is None:
        raise RuntimeError("Failed to override onboarding_state row")

    _record_audit(
        connection,
        guild_id=normalized_guild_id,
        actor_user_id=normalized_actor_id,
        action="onboarding.override",
        target_user_id=normalized_user_id,
        before=before,
        after=after,
    )
    return before, after
