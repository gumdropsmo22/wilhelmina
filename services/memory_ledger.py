from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import asdict, dataclass
from typing import Iterable

from services import audit_log
from services.database import utc_now_iso

MEMORY_SCHEMA_VERSION = 6

VALID_CATEGORIES = (
    "Identity",
    "Preference",
    "Dislike",
    "Boundary",
    "Interest",
    "Project",
    "Relationship context",
    "Communication style",
    "Important event",
    "Admin note",
    "Wilhelmina impression",
    "Gossip",
)
VALID_LABELS = ("Fact", "Inference", "Impression", "Gossip")
BLOCKED_PATTERNS = (
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(
        r"\b(?:api[ _-]?key|access[ _-]?token|refresh[ _-]?token|bearer token|login credential)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:bank account|routing number|credit card|debit card|cvv|iban)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:passport|national id|identity document|social security|ssn)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:diagnosed|diagnosis)\b", re.IGNORECASE),
    re.compile(r"\b(?:home address|residential address)\b", re.IGNORECASE),
)


class MemoryLedgerError(RuntimeError):
    """Base error for Memory Ledger operations."""


class MemoryNotFound(MemoryLedgerError):
    """Raised when a memory record cannot be found."""


class BlockedMemoryContent(MemoryLedgerError):
    """Raised when prohibited sensitive content is submitted."""


@dataclass(frozen=True)
class LedgerSettings:
    guild_id: int
    collection_enabled: bool
    wilhelmina_channel_id: int | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MemoryRecord:
    id: int
    guild_id: int
    subject_user_id: int
    category: str
    epistemic_label: str
    summary: str
    normalized_key: str
    topic_key: str
    is_gossip: bool
    active: bool
    created_by: int
    created_at: str
    updated_at: str
    last_confirmed_at: str


@dataclass(frozen=True)
class MemoryReceipt:
    id: int
    memory_id: int
    guild_id: int
    source_kind: str
    author_user_id: int
    channel_id: int | None
    message_id: int | None
    jump_url: str | None
    original_excerpt: str
    edited_excerpt: str | None
    source_created_at: str
    source_edited_at: str | None
    source_deleted_at: str | None
    created_at: str


@dataclass(frozen=True)
class MemoryContradiction:
    id: int
    guild_id: int
    left_memory_id: int
    right_memory_id: int
    topic_key: str
    created_at: str


@dataclass(frozen=True)
class UpsertResult:
    memory: MemoryRecord
    created: bool
    merged: bool
    replaced_memory_ids: tuple[int, ...]
    receipt: MemoryReceipt


SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS memory_ledger_settings (
        guild_id INTEGER PRIMARY KEY,
        collection_enabled INTEGER NOT NULL DEFAULT 1 CHECK (collection_enabled IN (0, 1)),
        wilhelmina_channel_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        subject_user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        epistemic_label TEXT NOT NULL,
        summary TEXT NOT NULL,
        normalized_key TEXT NOT NULL,
        topic_key TEXT NOT NULL,
        is_gossip INTEGER NOT NULL DEFAULT 0 CHECK (is_gossip IN (0, 1)),
        active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
        created_by INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_confirmed_at TEXT NOT NULL,
        FOREIGN KEY (guild_id, subject_user_id)
            REFERENCES coven_profile_shells (guild_id, user_id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_active_non_gossip_key
    ON memory_records (guild_id, subject_user_id, normalized_key)
    WHERE active = 1 AND is_gossip = 0
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_profile
    ON memory_records (guild_id, subject_user_id, active, category, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_gossip_topic
    ON memory_records (guild_id, subject_user_id, topic_key, is_gossip, active)
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        source_kind TEXT NOT NULL CHECK (source_kind IN ('discord', 'admin')),
        author_user_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER,
        jump_url TEXT,
        original_excerpt TEXT NOT NULL,
        edited_excerpt TEXT,
        source_created_at TEXT NOT NULL,
        source_edited_at TEXT,
        source_deleted_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (memory_id) REFERENCES memory_records (id) ON DELETE CASCADE,
        CHECK (
            (source_kind = 'admin' AND channel_id IS NULL AND message_id IS NULL AND jump_url IS NULL)
            OR
            (source_kind = 'discord' AND channel_id IS NOT NULL AND message_id IS NOT NULL AND jump_url IS NOT NULL)
        )
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_receipts_discord_message
    ON memory_receipts (memory_id, message_id)
    WHERE message_id IS NOT NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_receipts_message
    ON memory_receipts (guild_id, message_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_contradictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        left_memory_id INTEGER NOT NULL,
        right_memory_id INTEGER NOT NULL,
        topic_key TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (left_memory_id) REFERENCES memory_records (id) ON DELETE CASCADE,
        FOREIGN KEY (right_memory_id) REFERENCES memory_records (id) ON DELETE CASCADE,
        CHECK (left_memory_id < right_memory_id),
        UNIQUE (left_memory_id, right_memory_id)
    )
    """,
)


def initialize_memory_schema(connection: sqlite3.Connection) -> None:
    """Create the Registry dependency and Memory Ledger schema idempotently."""

    from services import coven_registry

    coven_registry.initialize_registry_schema(connection)
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
        (MEMORY_SCHEMA_VERSION, utc_now_iso()),
    )


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _row_to_settings(row: sqlite3.Row) -> LedgerSettings:
    return LedgerSettings(
        guild_id=int(row["guild_id"]),
        collection_enabled=bool(row["collection_enabled"]),
        wilhelmina_channel_id=_optional_int(row["wilhelmina_channel_id"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_memory(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        subject_user_id=int(row["subject_user_id"]),
        category=str(row["category"]),
        epistemic_label=str(row["epistemic_label"]),
        summary=str(row["summary"]),
        normalized_key=str(row["normalized_key"]),
        topic_key=str(row["topic_key"]),
        is_gossip=bool(row["is_gossip"]),
        active=bool(row["active"]),
        created_by=int(row["created_by"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        last_confirmed_at=str(row["last_confirmed_at"]),
    )


def _row_to_receipt(row: sqlite3.Row) -> MemoryReceipt:
    return MemoryReceipt(
        id=int(row["id"]),
        memory_id=int(row["memory_id"]),
        guild_id=int(row["guild_id"]),
        source_kind=str(row["source_kind"]),
        author_user_id=int(row["author_user_id"]),
        channel_id=_optional_int(row["channel_id"]),
        message_id=_optional_int(row["message_id"]),
        jump_url=row["jump_url"],
        original_excerpt=str(row["original_excerpt"]),
        edited_excerpt=row["edited_excerpt"],
        source_created_at=str(row["source_created_at"]),
        source_edited_at=row["source_edited_at"],
        source_deleted_at=row["source_deleted_at"],
        created_at=str(row["created_at"]),
    )


def _row_to_contradiction(row: sqlite3.Row) -> MemoryContradiction:
    return MemoryContradiction(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        left_memory_id=int(row["left_memory_id"]),
        right_memory_id=int(row["right_memory_id"]),
        topic_key=str(row["topic_key"]),
        created_at=str(row["created_at"]),
    )


def _clean_text(value: str, *, field: str, limit: int = 1000) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise MemoryLedgerError(f"{field} cannot be empty")
    if len(cleaned) > limit:
        raise MemoryLedgerError(f"{field} exceeds {limit} characters")
    return cleaned


def _validate_content(*values: str) -> None:
    joined = "\n".join(values)
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(joined):
            raise BlockedMemoryContent("Memory contains prohibited sensitive information")


def validate_extractable_text(text: str) -> str:
    """Reject prohibited information before text is sent to an external extractor."""

    cleaned = _clean_text(text, field="message text", limit=4000)
    _validate_content(cleaned)
    return cleaned


def normalize_memory_key(category: str, summary: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", summary.lower()).strip()
    return hashlib.sha256(f"{category.lower()}:{normalized}".encode("utf-8")).hexdigest()


def normalize_topic_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".", value.lower()).strip(".")
    if not normalized:
        raise MemoryLedgerError("topic_key cannot be empty")
    return normalized[:255]


def get_or_create_settings(connection: sqlite3.Connection, guild_id: int) -> LedgerSettings:
    initialize_memory_schema(connection)
    timestamp = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO memory_ledger_settings (
            guild_id, collection_enabled, wilhelmina_channel_id, created_at, updated_at
        ) VALUES (?, 1, NULL, ?, ?)
        """,
        (int(guild_id), timestamp, timestamp),
    )
    row = connection.execute(
        "SELECT * FROM memory_ledger_settings WHERE guild_id = ?", (int(guild_id),)
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to create Memory Ledger settings")
    return _row_to_settings(row)


def set_collection_enabled(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    enabled: bool,
    actor_user_id: int,
) -> LedgerSettings:
    before = get_or_create_settings(connection, guild_id)
    timestamp = utc_now_iso()
    connection.execute(
        "UPDATE memory_ledger_settings SET collection_enabled = ?, updated_at = ? WHERE guild_id = ?",
        (1 if enabled else 0, timestamp, int(guild_id)),
    )
    after = get_or_create_settings(connection, guild_id)
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="memory.collection_enabled" if enabled else "memory.collection_paused",
        target=str(guild_id),
        before=before,
        after=after,
    )
    return after


def set_wilhelmina_channel(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    channel_id: int | None,
    actor_user_id: int,
) -> LedgerSettings:
    before = get_or_create_settings(connection, guild_id)
    timestamp = utc_now_iso()
    connection.execute(
        "UPDATE memory_ledger_settings SET wilhelmina_channel_id = ?, updated_at = ? WHERE guild_id = ?",
        (_optional_int(channel_id), timestamp, int(guild_id)),
    )
    after = get_or_create_settings(connection, guild_id)
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="memory.channel_set",
        target=str(guild_id),
        before=before,
        after=after,
    )
    return after


def get_memory(
    connection: sqlite3.Connection,
    memory_id: int,
    *,
    required: bool = True,
) -> MemoryRecord | None:
    initialize_memory_schema(connection)
    row = connection.execute(
        "SELECT * FROM memory_records WHERE id = ?", (int(memory_id),)
    ).fetchone()
    if row is None and required:
        raise MemoryNotFound("No Memory Ledger record exists with that ID")
    return _row_to_memory(row) if row else None


def _insert_discord_receipt(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
    guild_id: int,
    author_user_id: int,
    channel_id: int,
    message_id: int,
    jump_url: str,
    excerpt: str,
    source_created_at: str,
) -> MemoryReceipt:
    timestamp = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO memory_receipts (
            memory_id, guild_id, source_kind, author_user_id, channel_id, message_id,
            jump_url, original_excerpt, source_created_at, created_at
        ) VALUES (?, ?, 'discord', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(memory_id),
            int(guild_id),
            int(author_user_id),
            int(channel_id),
            int(message_id),
            jump_url.strip(),
            excerpt.strip(),
            source_created_at,
            timestamp,
        ),
    )
    row = connection.execute(
        "SELECT * FROM memory_receipts WHERE memory_id = ? AND message_id = ?",
        (int(memory_id), int(message_id)),
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to create Discord memory receipt")
    return _row_to_receipt(row)


def _insert_admin_receipt(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
    guild_id: int,
    actor_user_id: int,
    excerpt: str,
) -> MemoryReceipt:
    timestamp = utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO memory_receipts (
            memory_id, guild_id, source_kind, author_user_id,
            original_excerpt, source_created_at, created_at
        ) VALUES (?, ?, 'admin', ?, ?, ?, ?)
        """,
        (int(memory_id), int(guild_id), int(actor_user_id), excerpt.strip(), timestamp, timestamp),
    )
    row = connection.execute(
        "SELECT * FROM memory_receipts WHERE id = ?", (int(cursor.lastrowid),)
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to create admin memory receipt")
    return _row_to_receipt(row)


def _record_contradictions_for_gossip(
    connection: sqlite3.Connection,
    memory: MemoryRecord,
) -> None:
    rows = connection.execute(
        """
        SELECT id FROM memory_records
        WHERE guild_id = ? AND subject_user_id = ? AND topic_key = ?
          AND is_gossip = 1 AND active = 1 AND id != ?
        """,
        (memory.guild_id, memory.subject_user_id, memory.topic_key, memory.id),
    ).fetchall()
    for row in rows:
        left_id, right_id = sorted((memory.id, int(row["id"])))
        connection.execute(
            """
            INSERT OR IGNORE INTO memory_contradictions (
                guild_id, left_memory_id, right_memory_id, topic_key, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (memory.guild_id, left_id, right_id, memory.topic_key, utc_now_iso()),
        )


def add_memory(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
    category: str,
    epistemic_label: str,
    summary: str,
    actor_user_id: int,
    topic_key: str | None = None,
    author_user_id: int | None = None,
    channel_id: int | None = None,
    message_id: int | None = None,
    jump_url: str | None = None,
    excerpt: str | None = None,
    source_created_at: str | None = None,
    replace_normal_category: bool = True,
) -> UpsertResult:
    """Create or merge a memory and permanently replace superseded ordinary records."""

    initialize_memory_schema(connection)
    category = _clean_text(category, field="category", limit=100)
    epistemic_label = _clean_text(epistemic_label, field="epistemic_label", limit=100)
    summary = _clean_text(summary, field="summary")
    if category not in VALID_CATEGORIES:
        raise MemoryLedgerError(f"Unknown memory category: {category}")
    if epistemic_label not in VALID_LABELS:
        raise MemoryLedgerError(f"Unknown epistemic label: {epistemic_label}")

    is_gossip = category == "Gossip" or epistemic_label == "Gossip"
    if is_gossip:
        category = "Gossip"
        epistemic_label = "Gossip"
    _validate_content(summary, excerpt or "")

    timestamp = utc_now_iso()
    duplicate_key = normalize_memory_key(category, summary)
    resolved_topic_key = normalize_topic_key(topic_key or summary)
    existing = connection.execute(
        """
        SELECT * FROM memory_records
        WHERE guild_id = ? AND subject_user_id = ? AND normalized_key = ? AND active = 1
        ORDER BY id DESC LIMIT 1
        """,
        (int(guild_id), int(subject_user_id), duplicate_key),
    ).fetchone()

    created = existing is None
    merged = existing is not None
    replaced_ids: list[int] = []

    if existing is not None:
        memory = _row_to_memory(existing)
        connection.execute(
            "UPDATE memory_records SET last_confirmed_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, memory.id),
        )
    else:
        if not is_gossip and replace_normal_category:
            rows = connection.execute(
                """
                SELECT id FROM memory_records
                WHERE guild_id = ? AND subject_user_id = ? AND category = ?
                  AND active = 1 AND is_gossip = 0
                """,
                (int(guild_id), int(subject_user_id), category),
            ).fetchall()
            replaced_ids = [int(row["id"]) for row in rows]
            for replaced_id in replaced_ids:
                connection.execute("DELETE FROM memory_records WHERE id = ?", (replaced_id,))
                audit_log.record_audit_event(
                    connection,
                    guild_id=guild_id,
                    actor_user_id=actor_user_id,
                    action="memory.replaced",
                    target=f"memory:{replaced_id}",
                    before=None,
                    after=None,
                )

        cursor = connection.execute(
            """
            INSERT INTO memory_records (
                guild_id, subject_user_id, category, epistemic_label, summary,
                normalized_key, topic_key, is_gossip, active, created_by,
                created_at, updated_at, last_confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                int(guild_id),
                int(subject_user_id),
                category,
                epistemic_label,
                summary,
                duplicate_key,
                resolved_topic_key,
                1 if is_gossip else 0,
                int(actor_user_id),
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        memory = get_memory(connection, int(cursor.lastrowid))
        if memory is None:
            raise RuntimeError("Failed to create memory")
        if memory.is_gossip:
            _record_contradictions_for_gossip(connection, memory)

    memory = get_memory(connection, memory.id)
    if memory is None:
        raise RuntimeError("Failed to load memory")

    discord_fields = (author_user_id, channel_id, message_id, jump_url, excerpt, source_created_at)
    if any(value is not None for value in discord_fields):
        if not all(value is not None for value in discord_fields):
            raise MemoryLedgerError("All Discord receipt fields are required together")
        receipt = _insert_discord_receipt(
            connection,
            memory_id=memory.id,
            guild_id=guild_id,
            author_user_id=int(author_user_id),
            channel_id=int(channel_id),
            message_id=int(message_id),
            jump_url=str(jump_url),
            excerpt=str(excerpt),
            source_created_at=str(source_created_at),
        )
    else:
        receipt = _insert_admin_receipt(
            connection,
            memory_id=memory.id,
            guild_id=guild_id,
            actor_user_id=actor_user_id,
            excerpt=summary,
        )

    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="memory.created" if created else "memory.confirmed",
        target=f"memory:{memory.id}",
        before=None,
        after=asdict(memory),
    )
    return UpsertResult(memory, created, merged, tuple(replaced_ids), receipt)


def update_memory(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
    actor_user_id: int,
    summary: str | None = None,
    category: str | None = None,
    epistemic_label: str | None = None,
    topic_key: str | None = None,
) -> MemoryRecord:
    before = get_memory(connection, memory_id)
    if before is None:
        raise MemoryNotFound("No Memory Ledger record exists with that ID")

    new_category = before.category if category is None else _clean_text(category, field="category", limit=100)
    new_label = before.epistemic_label if epistemic_label is None else _clean_text(
        epistemic_label, field="epistemic_label", limit=100
    )
    new_summary = before.summary if summary is None else _clean_text(summary, field="summary")
    new_topic = before.topic_key if topic_key is None else normalize_topic_key(topic_key)
    if new_category not in VALID_CATEGORIES or new_label not in VALID_LABELS:
        raise MemoryLedgerError("Invalid category or epistemic label")
    _validate_content(new_summary)

    is_gossip = new_category == "Gossip" or new_label == "Gossip"
    if is_gossip:
        new_category = new_label = "Gossip"
    timestamp = utc_now_iso()
    connection.execute(
        """
        UPDATE memory_records
        SET category = ?, epistemic_label = ?, summary = ?, normalized_key = ?,
            topic_key = ?, is_gossip = ?, updated_at = ?, last_confirmed_at = ?
        WHERE id = ?
        """,
        (
            new_category,
            new_label,
            new_summary,
            normalize_memory_key(new_category, new_summary),
            new_topic,
            1 if is_gossip else 0,
            timestamp,
            timestamp,
            int(memory_id),
        ),
    )
    after = get_memory(connection, memory_id)
    if after is None:
        raise RuntimeError("Failed to update memory")
    if after.is_gossip:
        _record_contradictions_for_gossip(connection, after)
    audit_log.record_audit_event(
        connection,
        guild_id=after.guild_id,
        actor_user_id=actor_user_id,
        action="memory.updated",
        target=f"memory:{after.id}",
        before=before,
        after=after,
    )
    return after


def delete_memory(connection: sqlite3.Connection, *, memory_id: int, actor_user_id: int) -> None:
    """Permanently delete a memory; receipts and contradiction links cascade."""

    memory = get_memory(connection, memory_id)
    if memory is None:
        raise MemoryNotFound("No Memory Ledger record exists with that ID")
    connection.execute("DELETE FROM memory_records WHERE id = ?", (int(memory_id),))
    audit_log.record_audit_event(
        connection,
        guild_id=memory.guild_id,
        actor_user_id=actor_user_id,
        action="memory.deleted",
        target=f"memory:{memory.id}",
        before=None,
        after=None,
    )


def list_profile(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
    include_inactive: bool = False,
) -> list[MemoryRecord]:
    initialize_memory_schema(connection)
    active_clause = "" if include_inactive else "AND active = 1"
    rows = connection.execute(
        f"""
        SELECT * FROM memory_records
        WHERE guild_id = ? AND subject_user_id = ? {active_clause}
        ORDER BY category ASC, updated_at DESC, id DESC
        """,
        (int(guild_id), int(subject_user_id)),
    ).fetchall()
    return [_row_to_memory(row) for row in rows]


def list_receipts(connection: sqlite3.Connection, memory_id: int) -> list[MemoryReceipt]:
    initialize_memory_schema(connection)
    rows = connection.execute(
        "SELECT * FROM memory_receipts WHERE memory_id = ? ORDER BY source_created_at ASC, id ASC",
        (int(memory_id),),
    ).fetchall()
    return [_row_to_receipt(row) for row in rows]


def list_contradictions(
    connection: sqlite3.Connection,
    *,
    memory_id: int | None = None,
) -> list[MemoryContradiction]:
    initialize_memory_schema(connection)
    if memory_id is None:
        rows = connection.execute(
            "SELECT * FROM memory_contradictions ORDER BY id ASC"
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT * FROM memory_contradictions
            WHERE left_memory_id = ? OR right_memory_id = ?
            ORDER BY id ASC
            """,
            (int(memory_id), int(memory_id)),
        ).fetchall()
    return [_row_to_contradiction(row) for row in rows]


def mark_message_edited(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    message_id: int,
    edited_excerpt: str,
    edited_at: str,
) -> int:
    validate_extractable_text(edited_excerpt)
    cursor = connection.execute(
        """
        UPDATE memory_receipts
        SET edited_excerpt = ?, source_edited_at = ?
        WHERE guild_id = ? AND message_id = ? AND source_kind = 'discord'
        """,
        (edited_excerpt.strip(), edited_at, int(guild_id), int(message_id)),
    )
    return int(cursor.rowcount)


def mark_message_deleted(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    message_id: int,
    deleted_at: str | None = None,
) -> int:
    cursor = connection.execute(
        """
        UPDATE memory_receipts
        SET source_deleted_at = ?
        WHERE guild_id = ? AND message_id = ? AND source_kind = 'discord'
        """,
        (deleted_at or utc_now_iso(), int(guild_id), int(message_id)),
    )
    return int(cursor.rowcount)


def render_profile_for_prompt(memories: Iterable[MemoryRecord]) -> str:
    rows = list(memories)
    if not rows:
        return "No saved memories."
    lines = ["MEMORY LEDGER — ACTIVE PROFILE"]
    for memory in rows:
        qualifier = "Unverified gossip" if memory.is_gossip else memory.epistemic_label
        lines.append(f"- [{memory.category} | {qualifier}] {memory.summary}")
    return "\n".join(lines)
