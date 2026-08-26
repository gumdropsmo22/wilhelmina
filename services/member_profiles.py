from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from services import audit_log
from services import coven_registry as registry
from services.database import utc_now_iso
from services.member_identity import (
    MemberIdentity,
    TrustedIdentityContext,
    normalize_discord_display_name,
)

MEMBER_IDENTITY_SCHEMA_VERSION = 8
# Legacy schema values retained only until the dedicated destructive migration tranche.
# They are historical/compatibility metadata and MUST NOT authorize memory or chat access.
LEGACY_MEMORY_CONSENT_VERSION = "legacy-adult-memory-v1"
CURRENT_MEMORY_CONSENT_VERSION = "2026-08-interaction-dm-cross-reveal-v2"
NON_AUTHORITATIVE_MEMORY_MARKER = "deprecated-not-authority"


class MemberIdentityProfileNotFound(LookupError):
    """Raised when a member has no completed identity profile."""


@dataclass(frozen=True)
class StoredMemberIdentity:
    """Private persisted identity joined with the current Discord-visible name."""

    guild_id: int
    user_id: int
    discord_display_name: str
    preferred_name: str
    birth_date: str
    # These two fields remain readable only because schema v8 still physically contains them.
    # Runtime authorization must use profile existence/source scope, never these values.
    adult_memory_consent_at: str
    memory_consent_version: str
    created_at: str
    updated_at: str

    def to_domain(self, *, today: date) -> MemberIdentity:
        """Revalidate persisted data before it enters a trusted conversational context."""

        return MemberIdentity.create(
            discord_display_name=self.discord_display_name,
            preferred_name=self.preferred_name,
            birth_date=self.birth_date,
            today=today,
        )

    def trusted_chat_context(self, *, on_date: date) -> TrustedIdentityContext:
        return self.to_domain(today=on_date).trusted_chat_context(on_date=on_date)

    @property
    def has_current_memory_consent(self) -> bool:
        """Legacy metadata only; never use this property as an authorization gate."""

        return self.memory_consent_version == CURRENT_MEMORY_CONSENT_VERSION


SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS coven_member_identity_profiles (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        preferred_name TEXT NOT NULL CHECK (
            length(trim(preferred_name)) BETWEEN 1 AND 80
        ),
        birth_date TEXT NOT NULL CHECK (birth_date GLOB '????-??-??'),
        adult_memory_consent_at TEXT NOT NULL,
        memory_consent_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id),
        FOREIGN KEY (guild_id, user_id)
            REFERENCES coven_registry_entries (guild_id, user_id)
            ON DELETE CASCADE
    )
    """,
)


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _migrate_legacy_memory_consent(connection: sqlite3.Connection) -> None:
    """Keep legacy schema v7 readable until the later physical column-removal migration."""

    columns = _column_names(connection, "coven_member_identity_profiles")
    if "memory_consent_version" in columns:
        return
    connection.execute(
        """
        ALTER TABLE coven_member_identity_profiles
        ADD COLUMN memory_consent_version TEXT NOT NULL
        DEFAULT 'legacy-adult-memory-v1'
        """
    )


def initialize_member_identity_schema(connection: sqlite3.Connection) -> None:
    """Create and migrate the private member-identity table idempotently."""

    registry.initialize_registry_schema(connection)
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    _migrate_legacy_memory_consent(connection)
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (version, applied_at)
        VALUES (?, ?)
        """,
        (MEMBER_IDENTITY_SCHEMA_VERSION, utc_now_iso()),
    )


def _row_to_identity(row: sqlite3.Row) -> StoredMemberIdentity:
    return StoredMemberIdentity(
        guild_id=int(row["guild_id"]),
        user_id=int(row["user_id"]),
        discord_display_name=str(row["display_name"]),
        preferred_name=str(row["preferred_name"]),
        birth_date=str(row["birth_date"]),
        adult_memory_consent_at=str(row["adult_memory_consent_at"]),
        memory_consent_version=str(row["memory_consent_version"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def get_member_identity(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    required: bool = False,
) -> StoredMemberIdentity | None:
    """Load one private identity profile, scoped to its Discord guild."""

    initialize_member_identity_schema(connection)
    row = connection.execute(
        """
        SELECT
            profile.guild_id,
            profile.user_id,
            entry.display_name,
            profile.preferred_name,
            profile.birth_date,
            profile.adult_memory_consent_at,
            profile.memory_consent_version,
            profile.created_at,
            profile.updated_at
        FROM coven_member_identity_profiles AS profile
        JOIN coven_registry_entries AS entry
          ON entry.guild_id = profile.guild_id
         AND entry.user_id = profile.user_id
        WHERE profile.guild_id = ? AND profile.user_id = ?
        """,
        (int(guild_id), int(user_id)),
    ).fetchone()
    if row is None and required:
        raise MemberIdentityProfileNotFound("Member identity profile has not been completed")
    return _row_to_identity(row) if row is not None else None


def profile_is_complete(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
) -> bool:
    """Return whether the member has a persisted identity profile."""

    return (
        get_member_identity(
            connection,
            guild_id=guild_id,
            user_id=user_id,
            required=False,
        )
        is not None
    )


def profile_is_memory_eligible(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
) -> bool:
    """Return whether identity prerequisites exist for approved memory interactions.

    This is intentionally profile-state based. Consent timestamps/versions left in schema v8
    are non-authoritative compatibility data and do not grant or revoke runtime access.
    """

    return profile_is_complete(
        connection,
        guild_id=guild_id,
        user_id=user_id,
    )


def profile_has_current_consent(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
) -> bool:
    """Deprecated compatibility alias for old Phase-4 callers.

    The old name survives temporarily so the reviewed extraction worker can remain mechanically
    stable in this tranche. It no longer checks consent and delegates to profile eligibility.
    """

    return profile_is_memory_eligible(
        connection,
        guild_id=guild_id,
        user_id=user_id,
    )


def save_member_identity(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    discord_display_name: str,
    preferred_name: str,
    birth_date: str | date,
    today: date,
    actor_user_id: int,
    adult_memory_consent: bool | None = None,
    consent_at: str | None = None,
    consent_version: str | None = None,
) -> StoredMemberIdentity:
    """Validate and persist the member's canonical private identity.

    The consent arguments are accepted only as short-lived source-compatibility parameters while
    schema v8 and older callers are being retired. Their values are ignored for authorization and
    new profiles receive a non-authoritative marker in the obsolete NOT NULL columns.
    """

    del adult_memory_consent, consent_at, consent_version
    initialize_member_identity_schema(connection)

    identity = MemberIdentity.create(
        discord_display_name=discord_display_name,
        preferred_name=preferred_name,
        birth_date=birth_date,
        today=today,
    )
    entry = registry.get_entry(
        connection,
        guild_id=int(guild_id),
        user_id=int(user_id),
        required=True,
    )
    assert entry is not None
    before = get_member_identity(
        connection,
        guild_id=int(guild_id),
        user_id=int(user_id),
        required=False,
    )
    timestamp = utc_now_iso()

    connection.execute(
        """
        UPDATE coven_registry_entries
        SET display_name = ?, updated_at = ?
        WHERE guild_id = ? AND user_id = ?
        """,
        (
            identity.discord_display_name,
            timestamp,
            int(guild_id),
            int(user_id),
        ),
    )
    connection.execute(
        """
        INSERT INTO coven_member_identity_profiles (
            guild_id,
            user_id,
            preferred_name,
            birth_date,
            adult_memory_consent_at,
            memory_consent_version,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (guild_id, user_id) DO UPDATE SET
            preferred_name = excluded.preferred_name,
            birth_date = excluded.birth_date,
            updated_at = excluded.updated_at
        """,
        (
            int(guild_id),
            int(user_id),
            identity.preferred_name,
            identity.birth_date.isoformat(),
            timestamp,
            NON_AUTHORITATIVE_MEMORY_MARKER,
            timestamp,
            timestamp,
        ),
    )

    after = get_member_identity(
        connection,
        guild_id=int(guild_id),
        user_id=int(user_id),
        required=True,
    )
    assert after is not None
    audit_log.record_audit_event(
        connection,
        guild_id=int(guild_id),
        actor_user_id=int(actor_user_id),
        action="identity.save",
        target=str(user_id),
        before={"profile_existed": before is not None},
        after={
            "profile_created": before is None,
            "discord_display_name_changed": entry.display_name != after.discord_display_name,
            "preferred_name_changed": before is None
            or before.preferred_name != after.preferred_name,
            "birth_date_changed": before is None or before.birth_date != after.birth_date,
        },
    )
    return after


def refresh_discord_display_name(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    discord_display_name: str,
    actor_user_id: int | None = None,
) -> registry.RegistryEntry:
    """Refresh the current screen name without overwriting the preferred name."""

    initialize_member_identity_schema(connection)
    normalized = normalize_discord_display_name(discord_display_name)
    before = registry.get_entry(
        connection,
        guild_id=int(guild_id),
        user_id=int(user_id),
        required=True,
    )
    assert before is not None
    if before.display_name == normalized:
        return before

    connection.execute(
        """
        UPDATE coven_registry_entries
        SET display_name = ?, updated_at = ?
        WHERE guild_id = ? AND user_id = ?
        """,
        (normalized, utc_now_iso(), int(guild_id), int(user_id)),
    )
    after = registry.get_entry(
        connection,
        guild_id=int(guild_id),
        user_id=int(user_id),
        required=True,
    )
    assert after is not None
    if actor_user_id is not None:
        audit_log.record_audit_event(
            connection,
            guild_id=int(guild_id),
            actor_user_id=int(actor_user_id),
            action="identity.refresh_discord_display_name",
            target=str(user_id),
            before={"display_name_changed": False},
            after={"display_name_changed": True},
        )
    return after


def get_trusted_identity_context(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    on_date: date,
) -> TrustedIdentityContext:
    """Build the allow-listed identity context for an already-authorized chat request."""

    stored = get_member_identity(
        connection,
        guild_id=int(guild_id),
        user_id=int(user_id),
        required=True,
    )
    assert stored is not None
    return stored.trusted_chat_context(on_date=on_date)
