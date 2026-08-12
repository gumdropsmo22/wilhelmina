from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from services import audit_log, memory_ledger


@dataclass(frozen=True)
class LedgerAdminSummary:
    settings: memory_ledger.LedgerSettings
    total_records: int
    active_records: int
    subject_count: int
    receipt_count: int
    gossip_records: int
    restricted_records: int
    admin_only_records: int
    contradiction_count: int
    integrity: memory_ledger.MemoryIntegrityReport


@dataclass(frozen=True)
class MemberMemorySummary:
    guild_id: int
    subject_user_id: int
    memory_count: int
    receipt_count: int
    gossip_count: int
    restricted_count: int
    admin_only_count: int


def summarize_ledger(connection: sqlite3.Connection, *, guild_id: int) -> LedgerAdminSummary:
    """Return content-free founder/admin diagnostics for one guild."""

    memory_ledger.initialize_memory_schema(connection)
    settings = memory_ledger.get_or_create_settings(connection, guild_id)
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total_records,
            SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active_records,
            COUNT(DISTINCT subject_user_id) AS subject_count,
            SUM(CASE WHEN is_gossip = 1 THEN 1 ELSE 0 END) AS gossip_records,
            SUM(CASE WHEN privacy_class = 'restricted' THEN 1 ELSE 0 END) AS restricted_records,
            SUM(CASE WHEN reveal_scope = 'admin_only' THEN 1 ELSE 0 END) AS admin_only_records
        FROM memory_records
        WHERE guild_id = ?
        """,
        (int(guild_id),),
    ).fetchone()
    receipt_count = int(
        connection.execute(
            "SELECT COUNT(*) AS count FROM memory_receipts WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()["count"]
    )
    contradiction_count = int(
        connection.execute(
            "SELECT COUNT(*) AS count FROM memory_contradictions WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()["count"]
    )
    integrity = memory_ledger.check_memory_integrity(connection)
    return LedgerAdminSummary(
        settings=settings,
        total_records=int(row["total_records"] or 0),
        active_records=int(row["active_records"] or 0),
        subject_count=int(row["subject_count"] or 0),
        receipt_count=receipt_count,
        gossip_records=int(row["gossip_records"] or 0),
        restricted_records=int(row["restricted_records"] or 0),
        admin_only_records=int(row["admin_only_records"] or 0),
        contradiction_count=contradiction_count,
        integrity=integrity,
    )


def summarize_member(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
) -> MemberMemorySummary:
    """Return content-free counts used for member data access/deletion administration."""

    memory_ledger.initialize_memory_schema(connection)
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS memory_count,
            SUM(CASE WHEN is_gossip = 1 THEN 1 ELSE 0 END) AS gossip_count,
            SUM(CASE WHEN privacy_class = 'restricted' THEN 1 ELSE 0 END) AS restricted_count,
            SUM(CASE WHEN reveal_scope = 'admin_only' THEN 1 ELSE 0 END) AS admin_only_count
        FROM memory_records
        WHERE guild_id = ? AND subject_user_id = ?
        """,
        (int(guild_id), int(subject_user_id)),
    ).fetchone()
    receipt_count = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_receipts AS receipts
            JOIN memory_records AS records ON records.id = receipts.memory_id
            WHERE records.guild_id = ? AND records.subject_user_id = ?
            """,
            (int(guild_id), int(subject_user_id)),
        ).fetchone()["count"]
    )
    return MemberMemorySummary(
        guild_id=int(guild_id),
        subject_user_id=int(subject_user_id),
        memory_count=int(row["memory_count"] or 0),
        receipt_count=receipt_count,
        gossip_count=int(row["gossip_count"] or 0),
        restricted_count=int(row["restricted_count"] or 0),
        admin_only_count=int(row["admin_only_count"] or 0),
    )


def delete_member_memories(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
    actor_user_id: int,
) -> int:
    """Permanently delete one subject's Memory Ledger rows and dependent evidence/indexes."""

    memory_ledger.initialize_memory_schema(connection)
    count = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count FROM memory_records
            WHERE guild_id = ? AND subject_user_id = ?
            """,
            (int(guild_id), int(subject_user_id)),
        ).fetchone()["count"]
    )
    connection.execute(
        "DELETE FROM memory_records WHERE guild_id = ? AND subject_user_id = ?",
        (int(guild_id), int(subject_user_id)),
    )
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="memory.member_deleted",
        target=f"member:{int(subject_user_id)}",
        before=None,
        after={"memory_count_deleted": count},
    )
    return count
