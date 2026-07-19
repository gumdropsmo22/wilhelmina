from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from services import audit_log
from services.database import utc_now_iso

REGISTRY_SCHEMA_VERSION = 5
CANONICAL_ID_RE = re.compile(r"^(?:⛧)?WTCH-(\d{4,})(?:⛧)?$", re.IGNORECASE)
VALID_CLASSIFICATIONS = ("Pending", "Initiate", "Recognized", "Bound", "Archived", "Banished")
VALID_STATUSES = ("active", "archived", "banished")


class RegistryError(RuntimeError):
    """Base error for Coven Registry operations."""


class RegistryNotBootstrapped(RegistryError):
    """Raised when member allocation is attempted before bootstrap."""


class RegistryEntryNotFound(RegistryError):
    """Raised when a registry entry cannot be found."""


@dataclass(frozen=True)
class RegistrySettings:
    guild_id: int
    founder_user_id: int
    public_channel_id: int | None
    next_number: int
    bootstrapped_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RegistryEntry:
    guild_id: int
    user_id: int
    registry_number: int
    canonical_id: str
    display_name: str
    classification: str
    status: str
    is_system: bool
    joined_at: str | None
    inducted_at: str | None
    departed_at: str | None
    covenant_version_id: int | None
    induction_notice_message_id: int | None
    created_at: str
    updated_at: str

    @property
    def display_mark(self) -> str:
        return display_mark(self.canonical_id)


@dataclass(frozen=True)
class ProfileShell:
    guild_id: int
    user_id: int
    memory_opt_out: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BootstrapResult:
    wilhelmina: RegistryEntry
    founder: RegistryEntry
    settings: RegistrySettings
    already_bootstrapped: bool


@dataclass(frozen=True)
class RegistrationResult:
    entry: RegistryEntry
    created: bool
    reactivated: bool


@dataclass(frozen=True)
class InductionResult:
    entry: RegistryEntry
    newly_inducted: bool
    notice_required: bool


@dataclass(frozen=True)
class RegistrySummary:
    guild_id: int
    total: int
    active: int
    pending: int
    initiated: int
    archived: int
    banished: int
    next_number: int | None
    public_channel_id: int | None


SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS coven_registry_settings (
        guild_id INTEGER PRIMARY KEY,
        founder_user_id INTEGER NOT NULL,
        public_channel_id INTEGER,
        next_number INTEGER NOT NULL DEFAULT 2 CHECK (next_number >= 2),
        bootstrapped_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS coven_registry_entries (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        registry_number INTEGER NOT NULL CHECK (registry_number >= 0),
        canonical_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        classification TEXT NOT NULL CHECK (
            classification IN ('Pending', 'Initiate', 'Recognized', 'Bound', 'Archived', 'Banished')
        ),
        status TEXT NOT NULL CHECK (status IN ('active', 'archived', 'banished')),
        is_system INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
        joined_at TEXT,
        inducted_at TEXT,
        departed_at TEXT,
        covenant_version_id INTEGER,
        induction_notice_message_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id),
        UNIQUE (guild_id, registry_number),
        UNIQUE (guild_id, canonical_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_coven_registry_public
    ON coven_registry_entries (guild_id, registry_number)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_coven_registry_classification
    ON coven_registry_entries (guild_id, classification, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS coven_profile_shells (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        memory_opt_out INTEGER NOT NULL DEFAULT 0 CHECK (memory_opt_out IN (0, 1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id),
        FOREIGN KEY (guild_id, user_id)
            REFERENCES coven_registry_entries (guild_id, user_id)
            ON DELETE CASCADE
    )
    """,
)


def initialize_registry_schema(connection: sqlite3.Connection) -> None:
    """Create Registry tables idempotently and record schema version 5."""

    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (version, applied_at)
        VALUES (?, ?)
        """,
        (REGISTRY_SCHEMA_VERSION, utc_now_iso()),
    )


def canonical_id(number: int) -> str:
    if int(number) < 0:
        raise RegistryError("registry number cannot be negative")
    return f"WTCH-{int(number):04d}"


def display_mark(value: str | int) -> str:
    canonical = canonical_id(value) if isinstance(value, int) else normalize_canonical_id(value)
    return f"⛧{canonical}⛧"


def normalize_canonical_id(value: str) -> str:
    text = value.strip().upper()
    match = CANONICAL_ID_RE.fullmatch(text)
    if match is None:
        raise RegistryError("Coven Mark must look like WTCH-0002 or ⛧WTCH-0002⛧")
    return canonical_id(int(match.group(1)))


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _row_to_settings(row: sqlite3.Row) -> RegistrySettings:
    return RegistrySettings(
        guild_id=int(row["guild_id"]),
        founder_user_id=int(row["founder_user_id"]),
        public_channel_id=_optional_int(row["public_channel_id"]),
        next_number=int(row["next_number"]),
        bootstrapped_at=str(row["bootstrapped_at"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_entry(row: sqlite3.Row) -> RegistryEntry:
    return RegistryEntry(
        guild_id=int(row["guild_id"]),
        user_id=int(row["user_id"]),
        registry_number=int(row["registry_number"]),
        canonical_id=str(row["canonical_id"]),
        display_name=str(row["display_name"]),
        classification=str(row["classification"]),
        status=str(row["status"]),
        is_system=bool(row["is_system"]),
        joined_at=row["joined_at"],
        inducted_at=row["inducted_at"],
        departed_at=row["departed_at"],
        covenant_version_id=_optional_int(row["covenant_version_id"]),
        induction_notice_message_id=_optional_int(row["induction_notice_message_id"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_profile_shell(row: sqlite3.Row) -> ProfileShell:
    return ProfileShell(
        guild_id=int(row["guild_id"]),
        user_id=int(row["user_id"]),
        memory_opt_out=bool(row["memory_opt_out"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def get_settings(connection: sqlite3.Connection, guild_id: int) -> RegistrySettings | None:
    initialize_registry_schema(connection)
    row = connection.execute(
        "SELECT * FROM coven_registry_settings WHERE guild_id = ?",
        (int(guild_id),),
    ).fetchone()
    return _row_to_settings(row) if row else None


def get_entry(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    required: bool = True,
) -> RegistryEntry | None:
    initialize_registry_schema(connection)
    row = connection.execute(
        """
        SELECT * FROM coven_registry_entries
        WHERE guild_id = ? AND user_id = ?
        """,
        (int(guild_id), int(user_id)),
    ).fetchone()
    if row is None and required:
        raise RegistryEntryNotFound("No Coven Registry entry exists for that member")
    return _row_to_entry(row) if row else None


def get_entry_by_mark(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    mark: str,
) -> RegistryEntry:
    initialize_registry_schema(connection)
    canonical = normalize_canonical_id(mark)
    row = connection.execute(
        """
        SELECT * FROM coven_registry_entries
        WHERE guild_id = ? AND canonical_id = ?
        """,
        (int(guild_id), canonical),
    ).fetchone()
    if row is None:
        raise RegistryEntryNotFound("No Coven Registry entry exists with that mark")
    return _row_to_entry(row)


def get_profile_shell(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
) -> ProfileShell | None:
    initialize_registry_schema(connection)
    row = connection.execute(
        """
        SELECT * FROM coven_profile_shells
        WHERE guild_id = ? AND user_id = ?
        """,
        (int(guild_id), int(user_id)),
    ).fetchone()
    return _row_to_profile_shell(row) if row else None


def _ensure_profile_shell(connection: sqlite3.Connection, entry: RegistryEntry) -> ProfileShell:
    timestamp = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO coven_profile_shells (
            guild_id, user_id, memory_opt_out, created_at, updated_at
        ) VALUES (?, ?, 0, ?, ?)
        """,
        (entry.guild_id, entry.user_id, timestamp, timestamp),
    )
    shell = get_profile_shell(connection, guild_id=entry.guild_id, user_id=entry.user_id)
    if shell is None:
        raise RuntimeError("Failed to create Coven Registry profile shell")
    return shell


def _insert_fixed_entry(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    number: int,
    display_name: str,
    classification: str,
    is_system: bool,
    joined_at: str | None,
) -> RegistryEntry:
    timestamp = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO coven_registry_entries (
            guild_id, user_id, registry_number, canonical_id, display_name,
            classification, status, is_system, joined_at, inducted_at,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
        """,
        (
            int(guild_id),
            int(user_id),
            int(number),
            canonical_id(number),
            display_name.strip() or canonical_id(number),
            classification,
            1 if is_system else 0,
            joined_at,
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    entry = get_entry(connection, guild_id=guild_id, user_id=user_id)
    if entry is None or entry.registry_number != number:
        raise RegistryError(f"Reserved Coven Mark {canonical_id(number)} is already occupied")
    if not is_system:
        _ensure_profile_shell(connection, entry)
    return entry


def bootstrap_registry(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    wilhelmina_user_id: int,
    founder_user_id: int,
    wilhelmina_name: str = "Wilhelmina",
    founder_name: str,
    founder_joined_at: str | None = None,
    actor_user_id: int,
) -> BootstrapResult:
    initialize_registry_schema(connection)
    existing = get_settings(connection, guild_id)
    already = existing is not None
    if existing is not None and existing.founder_user_id != int(founder_user_id):
        raise RegistryError("This Registry was already bootstrapped for a different founder")

    timestamp = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO coven_registry_settings (
            guild_id, founder_user_id, public_channel_id, next_number,
            bootstrapped_at, created_at, updated_at
        ) VALUES (?, ?, NULL, 2, ?, ?, ?)
        """,
        (int(guild_id), int(founder_user_id), timestamp, timestamp, timestamp),
    )
    wilhelmina = _insert_fixed_entry(
        connection,
        guild_id=guild_id,
        user_id=wilhelmina_user_id,
        number=0,
        display_name=wilhelmina_name,
        classification="Bound",
        is_system=True,
        joined_at=timestamp,
    )
    founder = _insert_fixed_entry(
        connection,
        guild_id=guild_id,
        user_id=founder_user_id,
        number=1,
        display_name=founder_name,
        classification="Bound",
        is_system=False,
        joined_at=founder_joined_at or timestamp,
    )
    settings = get_settings(connection, guild_id)
    if settings is None:
        raise RuntimeError("Failed to create Coven Registry settings")
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="registry.bootstrap",
        target=str(guild_id),
        before=None,
        after={
            "already_bootstrapped": already,
            "wilhelmina": asdict(wilhelmina),
            "founder": asdict(founder),
        },
    )
    return BootstrapResult(wilhelmina, founder, settings, already)


def register_pending_member(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    display_name: str,
    joined_at: str | None = None,
    actor_user_id: int | None = None,
) -> RegistrationResult:
    initialize_registry_schema(connection)
    settings = get_settings(connection, guild_id)
    if settings is None:
        raise RegistryNotBootstrapped("Bootstrap the Coven Registry before registering members")

    existing = get_entry(connection, guild_id=guild_id, user_id=user_id, required=False)
    timestamp = utc_now_iso()
    if existing is not None:
        reactivated = existing.status != "active"
        classification = existing.classification
        if classification in {"Archived", "Banished"}:
            classification = "Pending"
        connection.execute(
            """
            UPDATE coven_registry_entries
            SET display_name = ?, status = 'active', classification = ?,
                joined_at = COALESCE(?, joined_at), departed_at = NULL, updated_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (
                display_name.strip() or existing.display_name,
                classification,
                joined_at,
                timestamp,
                int(guild_id),
                int(user_id),
            ),
        )
        entry = get_entry(connection, guild_id=guild_id, user_id=user_id)
        assert entry is not None
        _ensure_profile_shell(connection, entry)
        return RegistrationResult(entry=entry, created=False, reactivated=reactivated)

    number = settings.next_number
    connection.execute(
        """
        INSERT INTO coven_registry_entries (
            guild_id, user_id, registry_number, canonical_id, display_name,
            classification, status, is_system, joined_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'Pending', 'active', 0, ?, ?, ?)
        """,
        (
            int(guild_id),
            int(user_id),
            number,
            canonical_id(number),
            display_name.strip() or canonical_id(number),
            joined_at or timestamp,
            timestamp,
            timestamp,
        ),
    )
    connection.execute(
        """
        UPDATE coven_registry_settings
        SET next_number = ?, updated_at = ?
        WHERE guild_id = ?
        """,
        (number + 1, timestamp, int(guild_id)),
    )
    entry = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert entry is not None
    _ensure_profile_shell(connection, entry)
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id or user_id,
        action="registry.register_pending",
        target=str(user_id),
        after=asdict(entry),
    )
    return RegistrationResult(entry=entry, created=True, reactivated=False)


def induct_member(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    covenant_version_id: int,
    accepted_at: str | None = None,
    actor_user_id: int | None = None,
) -> InductionResult:
    entry = get_entry(connection, guild_id=guild_id, user_id=user_id)
    if entry is None:
        raise RegistryEntryNotFound("No Coven Registry entry exists for induction")
    timestamp = accepted_at or utc_now_iso()
    newly_inducted = entry.inducted_at is None or entry.classification == "Pending"
    classification = "Initiate" if entry.classification == "Pending" else entry.classification
    connection.execute(
        """
        UPDATE coven_registry_entries
        SET classification = ?, status = 'active', inducted_at = COALESCE(inducted_at, ?),
            covenant_version_id = ?, departed_at = NULL, updated_at = ?
        WHERE guild_id = ? AND user_id = ?
        """,
        (
            classification,
            timestamp,
            int(covenant_version_id),
            utc_now_iso(),
            int(guild_id),
            int(user_id),
        ),
    )
    updated = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert updated is not None
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id or user_id,
        action="registry.induct",
        target=str(user_id),
        before=asdict(entry),
        after=asdict(updated),
    )
    return InductionResult(
        entry=updated,
        newly_inducted=newly_inducted,
        notice_required=newly_inducted and updated.induction_notice_message_id is None,
    )


def mark_induction_notice_published(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    message_id: int,
) -> RegistryEntry:
    connection.execute(
        """
        UPDATE coven_registry_entries
        SET induction_notice_message_id = ?, updated_at = ?
        WHERE guild_id = ? AND user_id = ?
        """,
        (int(message_id), utc_now_iso(), int(guild_id), int(user_id)),
    )
    entry = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert entry is not None
    return entry


def archive_member(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    actor_user_id: int,
) -> RegistryEntry | None:
    entry = get_entry(connection, guild_id=guild_id, user_id=user_id, required=False)
    if entry is None or entry.is_system:
        return entry
    classification = "Banished" if entry.classification == "Banished" else "Archived"
    status = "banished" if classification == "Banished" else "archived"
    timestamp = utc_now_iso()
    connection.execute(
        """
        UPDATE coven_registry_entries
        SET classification = ?, status = ?, departed_at = ?, updated_at = ?
        WHERE guild_id = ? AND user_id = ?
        """,
        (classification, status, timestamp, timestamp, int(guild_id), int(user_id)),
    )
    updated = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert updated is not None
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="registry.archive",
        target=str(user_id),
        before=asdict(entry),
        after=asdict(updated),
    )
    return updated


def set_classification(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    classification: str,
    actor_user_id: int,
) -> RegistryEntry:
    if classification not in VALID_CLASSIFICATIONS:
        raise RegistryError(f"classification must be one of {', '.join(VALID_CLASSIFICATIONS)}")
    before = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert before is not None
    status = before.status
    if classification == "Archived":
        status = "archived"
    elif classification == "Banished":
        status = "banished"
    elif status != "active":
        status = "active"
    connection.execute(
        """
        UPDATE coven_registry_entries
        SET classification = ?, status = ?, updated_at = ?
        WHERE guild_id = ? AND user_id = ?
        """,
        (classification, status, utc_now_iso(), int(guild_id), int(user_id)),
    )
    after = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert after is not None
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="registry.set_classification",
        target=str(user_id),
        before=asdict(before),
        after=asdict(after),
    )
    return after


def set_status(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    status: str,
    actor_user_id: int,
) -> RegistryEntry:
    normalized = status.strip().lower()
    if normalized not in VALID_STATUSES:
        raise RegistryError(f"status must be one of {', '.join(VALID_STATUSES)}")
    before = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert before is not None
    classification = before.classification
    if normalized == "archived":
        classification = "Archived"
    elif normalized == "banished":
        classification = "Banished"
    elif classification in {"Archived", "Banished"}:
        classification = "Pending"
    departed_at = utc_now_iso() if normalized != "active" else None
    connection.execute(
        """
        UPDATE coven_registry_entries
        SET status = ?, classification = ?, departed_at = ?, updated_at = ?
        WHERE guild_id = ? AND user_id = ?
        """,
        (
            normalized,
            classification,
            departed_at,
            utc_now_iso(),
            int(guild_id),
            int(user_id),
        ),
    )
    after = get_entry(connection, guild_id=guild_id, user_id=user_id)
    assert after is not None
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="registry.set_status",
        target=str(user_id),
        before=asdict(before),
        after=asdict(after),
    )
    return after


def set_public_channel(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    channel_id: int | None,
    actor_user_id: int,
) -> RegistrySettings:
    before = get_settings(connection, guild_id)
    if before is None:
        raise RegistryNotBootstrapped("Bootstrap the Coven Registry first")
    connection.execute(
        """
        UPDATE coven_registry_settings
        SET public_channel_id = ?, updated_at = ?
        WHERE guild_id = ?
        """,
        (channel_id, utc_now_iso(), int(guild_id)),
    )
    after = get_settings(connection, guild_id)
    assert after is not None
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="registry.set_public_channel",
        target=str(guild_id),
        before=asdict(before),
        after=asdict(after),
    )
    return after


def list_entries(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[RegistryEntry]:
    initialize_registry_schema(connection)
    bounded_limit = max(1, min(int(limit), 500))
    bounded_offset = max(0, int(offset))
    rows = connection.execute(
        """
        SELECT * FROM coven_registry_entries
        WHERE guild_id = ?
        ORDER BY registry_number ASC
        LIMIT ? OFFSET ?
        """,
        (int(guild_id), bounded_limit, bounded_offset),
    ).fetchall()
    return [_row_to_entry(row) for row in rows]


def count_entries(connection: sqlite3.Connection, *, guild_id: int) -> int:
    initialize_registry_schema(connection)
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM coven_registry_entries WHERE guild_id = ?",
        (int(guild_id),),
    ).fetchone()
    return int(row["count"] if row else 0)


def summarize_registry(connection: sqlite3.Connection, *, guild_id: int) -> RegistrySummary:
    initialize_registry_schema(connection)
    settings = get_settings(connection, guild_id)
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN classification = 'Pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN classification IN ('Initiate', 'Recognized', 'Bound') THEN 1 ELSE 0 END) AS initiated,
            SUM(CASE WHEN classification = 'Archived' THEN 1 ELSE 0 END) AS archived,
            SUM(CASE WHEN classification = 'Banished' THEN 1 ELSE 0 END) AS banished
        FROM coven_registry_entries
        WHERE guild_id = ?
        """,
        (int(guild_id),),
    ).fetchone()
    return RegistrySummary(
        guild_id=int(guild_id),
        total=int(row["total"] or 0),
        active=int(row["active"] or 0),
        pending=int(row["pending"] or 0),
        initiated=int(row["initiated"] or 0),
        archived=int(row["archived"] or 0),
        banished=int(row["banished"] or 0),
        next_number=settings.next_number if settings else None,
        public_channel_id=settings.public_channel_id if settings else None,
    )


def backfill_members(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    members: Iterable[tuple[int, str, str | None]],
    actor_user_id: int,
) -> list[RegistrationResult]:
    """Register existing human members in deterministic joined-time/user-id order."""

    ordered = sorted(members, key=lambda item: ((item[2] or ""), int(item[0])))
    results: list[RegistrationResult] = []
    for user_id, display_name, joined_at in ordered:
        results.append(
            register_pending_member(
                connection,
                guild_id=guild_id,
                user_id=user_id,
                display_name=display_name,
                joined_at=joined_at,
                actor_user_id=actor_user_id,
            )
        )
    return results
