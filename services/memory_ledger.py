from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable, Sequence

from services import audit_log
from services.database import utc_now_iso

MEMORY_SCHEMA_VERSION = 9

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
VALID_PRIVACY_CLASSES = ("ordinary", "restricted")
VALID_REVEAL_SCOPES = ("cross_member", "owner_only", "admin_only")
VALID_ENTITY_TYPES = ("subject", "member", "topic", "term")
RESERVED_ENTITY_TYPES = frozenset({"subject", "topic"})

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
    privacy_class: str
    reveal_scope: str
    importance: int
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
    source_context: str
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
class MemoryEntity:
    memory_id: int
    guild_id: int
    entity_type: str
    entity_key: str
    created_at: str


@dataclass(frozen=True)
class MemorySearchHit:
    memory: MemoryRecord
    rank: float


@dataclass(frozen=True)
class MemoryIntegrityReport:
    foreign_key_violations: int
    orphan_entities: int
    bad_contradictions: int
    missing_system_entities: int
    fts_available: bool

    @property
    def ok(self) -> bool:
        return (
            self.foreign_key_violations == 0
            and self.orphan_entities == 0
            and self.bad_contradictions == 0
            and self.missing_system_entities == 0
            and self.fts_available
        )


@dataclass(frozen=True)
class UpsertResult:
    memory: MemoryRecord
    created: bool
    merged: bool
    replaced_memory_ids: tuple[int, ...]
    receipt: MemoryReceipt


CREATE_RECEIPTS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('discord', 'admin')),
    source_context TEXT NOT NULL CHECK (source_context IN ('guild', 'dm', 'admin')),
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
        (
            source_kind = 'admin'
            AND source_context = 'admin'
            AND channel_id IS NULL
            AND message_id IS NULL
            AND jump_url IS NULL
        )
        OR
        (
            source_kind = 'discord'
            AND source_context = 'guild'
            AND channel_id IS NOT NULL
            AND message_id IS NOT NULL
            AND jump_url IS NOT NULL
        )
        OR
        (
            source_kind = 'discord'
            AND source_context = 'dm'
            AND message_id IS NOT NULL
            AND jump_url IS NULL
        )
    )
)
"""

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
        privacy_class TEXT NOT NULL DEFAULT 'ordinary'
            CHECK (privacy_class IN ('ordinary', 'restricted')),
        reveal_scope TEXT NOT NULL DEFAULT 'cross_member'
            CHECK (reveal_scope IN ('cross_member', 'owner_only', 'admin_only')),
        importance INTEGER NOT NULL DEFAULT 50 CHECK (importance BETWEEN 0 AND 100),
        created_by INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_confirmed_at TEXT NOT NULL,
        FOREIGN KEY (guild_id, subject_user_id)
            REFERENCES coven_profile_shells (guild_id, user_id)
            ON DELETE CASCADE
    )
    """,
    CREATE_RECEIPTS_TABLE,
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
    """
    CREATE TABLE IF NOT EXISTS memory_entities (
        memory_id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        entity_type TEXT NOT NULL CHECK (entity_type IN ('subject', 'member', 'topic', 'term')),
        entity_key TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (memory_id, entity_type, entity_key),
        FOREIGN KEY (memory_id) REFERENCES memory_records (id) ON DELETE CASCADE
    )
    """,
)


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _migration_applied(connection: sqlite3.Connection, version: int) -> bool:
    row = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?",
        (int(version),),
    ).fetchone()
    return row is not None


def _migrate_memory_records_v9(connection: sqlite3.Connection) -> None:
    columns = _column_names(connection, "memory_records")
    if "privacy_class" not in columns:
        connection.execute(
            "ALTER TABLE memory_records ADD COLUMN privacy_class TEXT NOT NULL DEFAULT 'ordinary'"
        )
    if "reveal_scope" not in columns:
        connection.execute(
            "ALTER TABLE memory_records ADD COLUMN reveal_scope TEXT NOT NULL DEFAULT 'cross_member'"
        )
    if "importance" not in columns:
        connection.execute(
            "ALTER TABLE memory_records ADD COLUMN importance INTEGER NOT NULL DEFAULT 50"
        )

    connection.execute(
        """
        UPDATE memory_records
        SET privacy_class = 'restricted', reveal_scope = 'admin_only'
        WHERE category = 'Admin note'
        """
    )


def _migrate_receipts_v9(connection: sqlite3.Connection) -> None:
    columns = _column_names(connection, "memory_receipts")
    if "source_context" in columns:
        return

    connection.execute("DROP INDEX IF EXISTS idx_memory_receipts_discord_message")
    connection.execute("DROP INDEX IF EXISTS idx_memory_receipts_message")
    connection.execute("ALTER TABLE memory_receipts RENAME TO memory_receipts_v6")
    connection.execute(CREATE_RECEIPTS_TABLE)
    connection.execute(
        """
        INSERT INTO memory_receipts (
            id, memory_id, guild_id, source_kind, source_context, author_user_id,
            channel_id, message_id, jump_url, original_excerpt, edited_excerpt,
            source_created_at, source_edited_at, source_deleted_at, created_at
        )
        SELECT
            id, memory_id, guild_id, source_kind,
            CASE WHEN source_kind = 'admin' THEN 'admin' ELSE 'guild' END,
            author_user_id, channel_id, message_id, jump_url, original_excerpt,
            edited_excerpt, source_created_at, source_edited_at, source_deleted_at,
            created_at
        FROM memory_receipts_v6
        """
    )
    connection.execute("DROP TABLE memory_receipts_v6")


def _ensure_record_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_active_non_gossip_key
        ON memory_records (guild_id, subject_user_id, normalized_key)
        WHERE active = 1 AND is_gossip = 0
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_profile
        ON memory_records (guild_id, subject_user_id, active, category, updated_at DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_gossip_topic
        ON memory_records (guild_id, subject_user_id, topic_key, is_gossip, active)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_reveal
        ON memory_records (guild_id, reveal_scope, active, importance DESC, updated_at DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_entities_lookup
        ON memory_entities (guild_id, entity_type, entity_key, memory_id)
        """
    )


def _ensure_receipt_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_receipts_discord_message
        ON memory_receipts (memory_id, message_id)
        WHERE message_id IS NOT NULL
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_receipts_message
        ON memory_receipts (guild_id, message_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_receipts_context
        ON memory_receipts (guild_id, source_context, source_created_at DESC)
        """
    )


def _ensure_memory_search(connection: sqlite3.Connection, *, rebuild: bool) -> None:
    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(
            summary,
            topic_key,
            content='memory_records',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS memory_records_search_ai
        AFTER INSERT ON memory_records BEGIN
            INSERT INTO memory_search(rowid, summary, topic_key)
            VALUES (new.id, new.summary, new.topic_key);
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS memory_records_search_ad
        AFTER DELETE ON memory_records BEGIN
            INSERT INTO memory_search(memory_search, rowid, summary, topic_key)
            VALUES ('delete', old.id, old.summary, old.topic_key);
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS memory_records_search_au
        AFTER UPDATE OF summary, topic_key ON memory_records BEGIN
            INSERT INTO memory_search(memory_search, rowid, summary, topic_key)
            VALUES ('delete', old.id, old.summary, old.topic_key);
            INSERT INTO memory_search(rowid, summary, topic_key)
            VALUES (new.id, new.summary, new.topic_key);
        END
        """
    )
    if rebuild:
        connection.execute("INSERT INTO memory_search(memory_search) VALUES ('rebuild')")


def initialize_memory_schema(connection: sqlite3.Connection) -> None:
    """Create and migrate the Memory Ledger schema idempotently."""

    from services import coven_registry

    coven_registry.initialize_registry_schema(connection)
    already_v9 = _migration_applied(connection, MEMORY_SCHEMA_VERSION)
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)

    # Existing v6 tables must gain v9 columns before indexes reference them.
    _migrate_memory_records_v9(connection)
    _migrate_receipts_v9(connection)
    _ensure_record_indexes(connection)
    _ensure_receipt_indexes(connection)
    _ensure_memory_search(connection, rebuild=not already_v9)
    if not already_v9:
        _backfill_system_entities(connection)
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
        privacy_class=str(row["privacy_class"]),
        reveal_scope=str(row["reveal_scope"]),
        importance=int(row["importance"]),
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
        source_context=str(row["source_context"]),
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


def _row_to_entity(row: sqlite3.Row) -> MemoryEntity:
    return MemoryEntity(
        memory_id=int(row["memory_id"]),
        guild_id=int(row["guild_id"]),
        entity_type=str(row["entity_type"]),
        entity_key=str(row["entity_key"]),
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


def normalize_entity_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", ".", value.lower()).strip(".")
    if not normalized:
        raise MemoryLedgerError("entity_key cannot be empty")
    return normalized[:255]


def _validate_entity_type(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if normalized not in VALID_ENTITY_TYPES:
        allowed = ", ".join(VALID_ENTITY_TYPES)
        raise MemoryLedgerError(f"entity_type must be one of: {allowed}")
    return normalized


def _resolve_privacy(
    *,
    category: str,
    privacy_class: str | None,
    reveal_scope: str | None,
) -> tuple[str, str]:
    if category == "Admin note":
        return "restricted", "admin_only"

    resolved_privacy = (privacy_class or "ordinary").strip().lower()
    resolved_scope = (reveal_scope or "cross_member").strip().lower()
    if resolved_privacy not in VALID_PRIVACY_CLASSES:
        raise MemoryLedgerError("Invalid privacy_class")
    if resolved_scope not in VALID_REVEAL_SCOPES:
        raise MemoryLedgerError("Invalid reveal_scope")
    if resolved_privacy == "restricted" and resolved_scope == "cross_member":
        raise MemoryLedgerError("Restricted memories cannot use cross_member reveal scope")
    return resolved_privacy, resolved_scope


def _validate_importance(value: int) -> int:
    importance = int(value)
    if not 0 <= importance <= 100:
        raise MemoryLedgerError("importance must be between 0 and 100")
    return importance


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


def _insert_entity(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
    guild_id: int,
    entity_type: str,
    entity_key: str,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO memory_entities (
            memory_id, guild_id, entity_type, entity_key, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(memory_id),
            int(guild_id),
            _validate_entity_type(entity_type),
            normalize_entity_key(entity_key),
            utc_now_iso(),
        ),
    )


def _sync_system_entities(connection: sqlite3.Connection, memory: MemoryRecord) -> None:
    connection.execute(
        "DELETE FROM memory_entities WHERE memory_id = ? AND entity_type IN ('subject', 'topic')",
        (int(memory.id),),
    )
    _insert_entity(
        connection,
        memory_id=memory.id,
        guild_id=memory.guild_id,
        entity_type="subject",
        entity_key=str(memory.subject_user_id),
    )
    _insert_entity(
        connection,
        memory_id=memory.id,
        guild_id=memory.guild_id,
        entity_type="topic",
        entity_key=memory.topic_key,
    )


def _backfill_system_entities(connection: sqlite3.Connection) -> None:
    rows = connection.execute("SELECT * FROM memory_records ORDER BY id ASC").fetchall()
    for row in rows:
        _sync_system_entities(connection, _row_to_memory(row))


def set_memory_entities(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
    entities: Iterable[tuple[str, str]],
) -> list[MemoryEntity]:
    """Replace non-system entity links while preserving subject/topic indexes."""

    memory = get_memory(connection, memory_id)
    if memory is None:
        raise MemoryNotFound("No Memory Ledger record exists with that ID")
    normalized_entities: list[tuple[str, str]] = []
    for entity_type, entity_key in entities:
        normalized_type = _validate_entity_type(entity_type)
        if normalized_type in RESERVED_ENTITY_TYPES:
            raise MemoryLedgerError("subject/topic entity links are managed by the Memory Ledger")
        normalized_entities.append((normalized_type, normalize_entity_key(entity_key)))

    connection.execute(
        "DELETE FROM memory_entities WHERE memory_id = ? AND entity_type NOT IN ('subject', 'topic')",
        (int(memory_id),),
    )
    for entity_type, entity_key in normalized_entities:
        _insert_entity(
            connection,
            memory_id=memory.id,
            guild_id=memory.guild_id,
            entity_type=entity_type,
            entity_key=entity_key,
        )
    _sync_system_entities(connection, memory)
    return list_memory_entities(connection, memory_id=memory.id)


def list_memory_entities(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
) -> list[MemoryEntity]:
    initialize_memory_schema(connection)
    rows = connection.execute(
        """
        SELECT * FROM memory_entities
        WHERE memory_id = ?
        ORDER BY entity_type ASC, entity_key ASC
        """,
        (int(memory_id),),
    ).fetchall()
    return [_row_to_entity(row) for row in rows]


def _insert_discord_receipt(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
    guild_id: int,
    source_context: str,
    author_user_id: int,
    channel_id: int | None,
    message_id: int,
    jump_url: str | None,
    excerpt: str,
    source_created_at: str,
) -> MemoryReceipt:
    resolved_context = source_context.strip().lower()
    if resolved_context not in {"guild", "dm"}:
        raise MemoryLedgerError("Discord source_context must be guild or dm")
    if resolved_context == "guild" and (channel_id is None or not jump_url):
        raise MemoryLedgerError("Guild Discord receipts require channel_id and jump_url")
    if resolved_context == "dm" and jump_url is not None:
        raise MemoryLedgerError("DM receipts must not fabricate a guild jump_url")

    timestamp = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO memory_receipts (
            memory_id, guild_id, source_kind, source_context, author_user_id,
            channel_id, message_id, jump_url, original_excerpt,
            source_created_at, created_at
        ) VALUES (?, ?, 'discord', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(memory_id),
            int(guild_id),
            resolved_context,
            int(author_user_id),
            _optional_int(channel_id),
            int(message_id),
            jump_url.strip() if jump_url else None,
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
            memory_id, guild_id, source_kind, source_context, author_user_id,
            original_excerpt, source_created_at, created_at
        ) VALUES (?, ?, 'admin', 'admin', ?, ?, ?, ?)
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
    source_context: str | None = None,
    privacy_class: str | None = None,
    reveal_scope: str | None = None,
    importance: int = 50,
    replace_normal_category: bool = True,
) -> UpsertResult:
    """Create/merge a memory and replace only superseded ordinary same-topic records.

    `replace_normal_category` is retained for backward compatibility. In schema v9 the
    flag controls topic-scoped replacement rather than category-wide deletion.
    """

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

    resolved_privacy, resolved_scope = _resolve_privacy(
        category=category,
        privacy_class=privacy_class,
        reveal_scope=reveal_scope,
    )
    resolved_importance = _validate_importance(importance)
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
                WHERE guild_id = ? AND subject_user_id = ? AND topic_key = ?
                  AND active = 1 AND is_gossip = 0
                """,
                (int(guild_id), int(subject_user_id), resolved_topic_key),
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
                normalized_key, topic_key, is_gossip, active, privacy_class,
                reveal_scope, importance, created_by, created_at, updated_at,
                last_confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
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
                resolved_privacy,
                resolved_scope,
                resolved_importance,
                int(actor_user_id),
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        memory = get_memory(connection, int(cursor.lastrowid))
        if memory is None:
            raise RuntimeError("Failed to create memory")
        _sync_system_entities(connection, memory)
        if memory.is_gossip:
            _record_contradictions_for_gossip(connection, memory)

    memory = get_memory(connection, memory.id)
    if memory is None:
        raise RuntimeError("Failed to load memory")

    discord_requested = any(
        value is not None
        for value in (author_user_id, channel_id, message_id, jump_url, excerpt, source_created_at)
    ) or source_context in {"guild", "dm"}
    if discord_requested:
        if author_user_id is None or message_id is None or excerpt is None or source_created_at is None:
            raise MemoryLedgerError(
                "Discord receipts require author_user_id, message_id, excerpt, and source_created_at"
            )
        resolved_context = (source_context or "guild").strip().lower()
        receipt = _insert_discord_receipt(
            connection,
            memory_id=memory.id,
            guild_id=guild_id,
            source_context=resolved_context,
            author_user_id=int(author_user_id),
            channel_id=_optional_int(channel_id),
            message_id=int(message_id),
            jump_url=jump_url,
            excerpt=str(excerpt),
            source_created_at=str(source_created_at),
        )
    else:
        if source_context not in {None, "admin"}:
            raise MemoryLedgerError("Admin memories may only use source_context='admin'")
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
        after={
            "memory_id": memory.id,
            "created": created,
            "merged": merged,
            "privacy_class": memory.privacy_class,
            "reveal_scope": memory.reveal_scope,
            "source_context": receipt.source_context,
        },
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
    privacy_class: str | None = None,
    reveal_scope: str | None = None,
    importance: int | None = None,
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
    new_privacy, new_scope = _resolve_privacy(
        category=new_category,
        privacy_class=before.privacy_class if privacy_class is None else privacy_class,
        reveal_scope=before.reveal_scope if reveal_scope is None else reveal_scope,
    )
    new_importance = before.importance if importance is None else _validate_importance(importance)

    connection.execute(
        "DELETE FROM memory_contradictions WHERE left_memory_id = ? OR right_memory_id = ?",
        (int(memory_id), int(memory_id)),
    )
    timestamp = utc_now_iso()
    connection.execute(
        """
        UPDATE memory_records
        SET category = ?, epistemic_label = ?, summary = ?, normalized_key = ?,
            topic_key = ?, is_gossip = ?, privacy_class = ?, reveal_scope = ?,
            importance = ?, updated_at = ?, last_confirmed_at = ?
        WHERE id = ?
        """,
        (
            new_category,
            new_label,
            new_summary,
            normalize_memory_key(new_category, new_summary),
            new_topic,
            1 if is_gossip else 0,
            new_privacy,
            new_scope,
            new_importance,
            timestamp,
            timestamp,
            int(memory_id),
        ),
    )
    after = get_memory(connection, memory_id)
    if after is None:
        raise RuntimeError("Failed to update memory")
    _sync_system_entities(connection, after)
    if after.is_gossip:
        _record_contradictions_for_gossip(connection, after)
    audit_log.record_audit_event(
        connection,
        guild_id=after.guild_id,
        actor_user_id=actor_user_id,
        action="memory.updated",
        target=f"memory:{after.id}",
        before=None,
        after={
            "memory_id": after.id,
            "summary_changed": before.summary != after.summary,
            "category_changed": before.category != after.category,
            "label_changed": before.epistemic_label != after.epistemic_label,
            "topic_changed": before.topic_key != after.topic_key,
            "privacy_changed": before.privacy_class != after.privacy_class,
            "reveal_scope_changed": before.reveal_scope != after.reveal_scope,
            "importance_changed": before.importance != after.importance,
        },
    )
    return after


def delete_memory(connection: sqlite3.Connection, *, memory_id: int, actor_user_id: int) -> None:
    """Permanently delete a memory and every dependent row."""

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
        ORDER BY category ASC, importance DESC, updated_at DESC, id DESC
        """,
        (int(guild_id), int(subject_user_id)),
    ).fetchall()
    return [_row_to_memory(row) for row in rows]


def memory_is_revealable(
    memory: MemoryRecord,
    *,
    interlocutor_user_id: int,
    allow_admin: bool = False,
) -> bool:
    if memory.reveal_scope == "admin_only":
        return allow_admin
    if memory.reveal_scope == "owner_only":
        return memory.subject_user_id == int(interlocutor_user_id)
    return memory.reveal_scope == "cross_member"


def list_revealable_profile(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
    interlocutor_user_id: int,
    allow_admin: bool = False,
) -> list[MemoryRecord]:
    return [
        memory
        for memory in list_profile(
            connection,
            guild_id=guild_id,
            subject_user_id=subject_user_id,
        )
        if memory_is_revealable(
            memory,
            interlocutor_user_id=interlocutor_user_id,
            allow_admin=allow_admin,
        )
    ]


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


def _normalize_search_query(query: str) -> str:
    cleaned = _clean_text(query, field="search query", limit=500)
    tokens = re.findall(r"[a-z0-9]+", cleaned.lower())[:12]
    if not tokens:
        raise MemoryLedgerError("search query contains no searchable terms")
    return " AND ".join(f'"{token}"' for token in tokens)


def _validate_reveal_scopes(reveal_scopes: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(scope.strip().lower() for scope in reveal_scopes)
    if not normalized:
        raise MemoryLedgerError("At least one reveal scope is required")
    if any(scope not in VALID_REVEAL_SCOPES for scope in normalized):
        raise MemoryLedgerError("Invalid reveal scope filter")
    return normalized


def search_memories(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    query: str,
    reveal_scopes: Sequence[str] = ("cross_member",),
    subject_user_ids: Sequence[int] | None = None,
    limit: int = 20,
) -> list[MemorySearchHit]:
    """Search active memories locally with FTS5 and deterministic scope filters."""

    initialize_memory_schema(connection)
    resolved_scopes = _validate_reveal_scopes(reveal_scopes)
    resolved_limit = max(1, min(int(limit), 100))
    query_sql = _normalize_search_query(query)
    scope_placeholders = ", ".join("?" for _ in resolved_scopes)
    subject_clause = ""
    params: list[object] = [query_sql, int(guild_id), *resolved_scopes]
    if subject_user_ids:
        subject_ids = tuple(int(value) for value in subject_user_ids)
        subject_placeholders = ", ".join("?" for _ in subject_ids)
        subject_clause = f"AND records.subject_user_id IN ({subject_placeholders})"
        params.extend(subject_ids)
    params.append(resolved_limit)
    rows = connection.execute(
        f"""
        SELECT records.*, bm25(memory_search) AS search_rank
        FROM memory_search
        JOIN memory_records AS records ON records.id = memory_search.rowid
        WHERE memory_search MATCH ?
          AND records.guild_id = ?
          AND records.active = 1
          AND records.reveal_scope IN ({scope_placeholders})
          {subject_clause}
        ORDER BY search_rank ASC, records.importance DESC, records.updated_at DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [
        MemorySearchHit(memory=_row_to_memory(row), rank=float(row["search_rank"]))
        for row in rows
    ]


def find_memories_by_entity(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    entity_type: str,
    entity_key: str,
    reveal_scopes: Sequence[str] = ("cross_member",),
    limit: int = 50,
) -> list[MemoryRecord]:
    initialize_memory_schema(connection)
    resolved_type = _validate_entity_type(entity_type)
    resolved_key = normalize_entity_key(entity_key)
    resolved_scopes = _validate_reveal_scopes(reveal_scopes)
    resolved_limit = max(1, min(int(limit), 100))
    placeholders = ", ".join("?" for _ in resolved_scopes)
    rows = connection.execute(
        f"""
        SELECT records.*
        FROM memory_entities AS entities
        JOIN memory_records AS records ON records.id = entities.memory_id
        WHERE entities.guild_id = ?
          AND entities.entity_type = ?
          AND entities.entity_key = ?
          AND records.active = 1
          AND records.reveal_scope IN ({placeholders})
        ORDER BY records.importance DESC, records.updated_at DESC, records.id DESC
        LIMIT ?
        """,
        (int(guild_id), resolved_type, resolved_key, *resolved_scopes, resolved_limit),
    ).fetchall()
    return [_row_to_memory(row) for row in rows]


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


def check_memory_integrity(connection: sqlite3.Connection) -> MemoryIntegrityReport:
    initialize_memory_schema(connection)
    foreign_key_violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    orphan_entities = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_entities AS entities
            LEFT JOIN memory_records AS records ON records.id = entities.memory_id
            WHERE records.id IS NULL OR records.guild_id != entities.guild_id
            """
        ).fetchone()["count"]
    )
    bad_contradictions = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_contradictions AS links
            LEFT JOIN memory_records AS left_record ON left_record.id = links.left_memory_id
            LEFT JOIN memory_records AS right_record ON right_record.id = links.right_memory_id
            WHERE left_record.id IS NULL
               OR right_record.id IS NULL
               OR left_record.guild_id != links.guild_id
               OR right_record.guild_id != links.guild_id
               OR left_record.topic_key != links.topic_key
               OR right_record.topic_key != links.topic_key
               OR left_record.is_gossip != 1
               OR right_record.is_gossip != 1
            """
        ).fetchone()["count"]
    )
    missing_system_entities = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_records AS records
            WHERE NOT EXISTS (
                SELECT 1 FROM memory_entities AS subject_entity
                WHERE subject_entity.memory_id = records.id
                  AND subject_entity.entity_type = 'subject'
                  AND subject_entity.entity_key = CAST(records.subject_user_id AS TEXT)
            )
            OR NOT EXISTS (
                SELECT 1 FROM memory_entities AS topic_entity
                WHERE topic_entity.memory_id = records.id
                  AND topic_entity.entity_type = 'topic'
                  AND topic_entity.entity_key = records.topic_key
            )
            """
        ).fetchone()["count"]
    )
    fts_available = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memory_search'"
    ).fetchone() is not None
    return MemoryIntegrityReport(
        foreign_key_violations=foreign_key_violations,
        orphan_entities=orphan_entities,
        bad_contradictions=bad_contradictions,
        missing_system_entities=missing_system_entities,
        fts_available=fts_available,
    )


def render_profile_for_prompt(memories: Iterable[MemoryRecord]) -> str:
    rows = list(memories)
    if not rows:
        return "No saved memories."
    lines = ["MEMORY LEDGER — ACTIVE PROFILE"]
    for memory in rows:
        qualifier = "Unverified gossip" if memory.is_gossip else memory.epistemic_label
        lines.append(f"- [{memory.category} | {qualifier}] {memory.summary}")
    return "\n".join(lines)
