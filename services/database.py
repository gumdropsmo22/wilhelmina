from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

CURRENT_SCHEMA_VERSION = 3
DEFAULT_DATABASE_PATH = Path("data/wilhelmina.sqlite3")

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS guild_config (
        guild_id INTEGER PRIMARY KEY,
        admin_role_id INTEGER,
        member_role_id INTEGER,
        pending_role_id INTEGER,
        welcome_channel_id INTEGER,
        onboarding_channel_id INTEGER,
        broadcast_channel_id INTEGER,
        admin_log_channel_id INTEGER,
        timezone TEXT NOT NULL DEFAULT 'UTC',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        actor_user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        before_json TEXT,
        after_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_log_guild_created
    ON audit_log (guild_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS onboarding_state (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        state TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        approved_by INTEGER,
        rejected_by INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_onboarding_state_guild_state
    ON onboarding_state (guild_id, state, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS rules_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        version_tag TEXT NOT NULL,
        title TEXT NOT NULL,
        intro_text TEXT NOT NULL,
        body_text TEXT NOT NULL,
        accept_label TEXT NOT NULL DEFAULT 'I accept the covenant',
        is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
        published_channel_id INTEGER,
        published_message_id INTEGER,
        created_by INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (guild_id, version_tag)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_rules_versions_active
    ON rules_versions (guild_id)
    WHERE is_active = 1
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_rules_versions_guild_updated
    ON rules_versions (guild_id, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS rules_acceptance (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rules_version_id INTEGER NOT NULL,
        accepted_via TEXT NOT NULL,
        accepted_at TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id, rules_version_id),
        FOREIGN KEY (rules_version_id)
            REFERENCES rules_versions (id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_rules_acceptance_guild_user
    ON rules_acceptance (guild_id, user_id, accepted_at DESC)
    """,
)


def utc_now_iso() -> str:
    """Return a compact UTC timestamp for database records."""

    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_database_path(database_path: str | Path | None = None) -> Path:
    """Normalize a configured SQLite path without creating it."""

    if database_path is None:
        return DEFAULT_DATABASE_PATH

    path = Path(database_path).expanduser()
    if str(path).strip() == "":
        raise ValueError("database_path cannot be empty")

    return path


def connect(database_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with Wilhelmina's default pragmas."""

    path = normalize_database_path(database_path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def managed_connection(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a committing SQLite connection and rollback on error."""

    connection = connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: str | Path) -> None:
    """Create Wilhelmina's SQLite schema idempotently."""

    path = normalize_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with managed_connection(path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)

        connection.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, applied_at)
            VALUES (?, ?)
            """,
            (CURRENT_SCHEMA_VERSION, utc_now_iso()),
        )


def fetch_schema_versions(connection: sqlite3.Connection) -> list[int]:
    """Return applied schema versions in ascending order."""

    rows = connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version ASC"
    ).fetchall()
    return [int(row["version"]) for row in rows]
