from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from services import audit_log, memory_ledger

_REVEAL_SCOPE_RANK = {
    "cross_member": 0,
    "owner_only": 1,
    "admin_only": 2,
}


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
    subject_receipt_count: int
    authored_cross_subject_receipt_count: int
    gossip_count: int
    restricted_count: int
    admin_only_count: int


@dataclass(frozen=True)
class MemberMemoryDeletionResult:
    guild_id: int
    subject_user_id: int
    subject_memory_count_deleted: int
    authored_cross_subject_receipt_count_deleted: int
    evidence_orphan_memory_count_deleted: int

    @property
    def memory_count_deleted(self) -> int:
        return self.subject_memory_count_deleted + self.evidence_orphan_memory_count_deleted


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
    """Return content-free counts for every Memory Ledger row tied to one member."""

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
    subject_receipt_count = int(
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
    authored_cross_subject_receipt_count = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_receipts AS receipts
            JOIN memory_records AS records ON records.id = receipts.memory_id
            WHERE records.guild_id = ?
              AND records.subject_user_id != ?
              AND receipts.author_user_id = ?
            """,
            (int(guild_id), int(subject_user_id), int(subject_user_id)),
        ).fetchone()["count"]
    )
    return MemberMemorySummary(
        guild_id=int(guild_id),
        subject_user_id=int(subject_user_id),
        memory_count=int(row["memory_count"] or 0),
        receipt_count=subject_receipt_count + authored_cross_subject_receipt_count,
        subject_receipt_count=subject_receipt_count,
        authored_cross_subject_receipt_count=authored_cross_subject_receipt_count,
        gossip_count=int(row["gossip_count"] or 0),
        restricted_count=int(row["restricted_count"] or 0),
        admin_only_count=int(row["admin_only_count"] or 0),
    )


def _stricter_privacy(
    *,
    existing_privacy: str,
    existing_scope: str,
    requested_privacy: str,
    requested_scope: str,
) -> tuple[str, str]:
    privacy = (
        "restricted"
        if "restricted" in {existing_privacy, requested_privacy}
        else "ordinary"
    )
    scope = max(
        (existing_scope, requested_scope),
        key=lambda value: _REVEAL_SCOPE_RANK[value],
    )
    if privacy == "restricted" and scope == "cross_member":
        scope = "owner_only"
    return privacy, scope


def add_admin_memory(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
    category: str,
    epistemic_label: str,
    summary: str,
    topic_key: str | None,
    actor_user_id: int,
    privacy_class: str,
    reveal_scope: str,
    importance: int,
) -> tuple[memory_ledger.MemoryWriteResult, memory_ledger.MemoryRecord]:
    """Add/confirm an admin memory while allowing duplicate privacy to tighten, never loosen."""

    result = memory_ledger.add_memory(
        connection,
        guild_id=guild_id,
        subject_user_id=subject_user_id,
        category=category,
        epistemic_label=epistemic_label,
        summary=summary,
        topic_key=topic_key,
        actor_user_id=actor_user_id,
        source_context="admin",
        privacy_class=privacy_class,
        reveal_scope=reveal_scope,
        importance=importance,
    )
    stored = result.memory
    if not result.created:
        tightened_privacy, tightened_scope = _stricter_privacy(
            existing_privacy=stored.privacy_class,
            existing_scope=stored.reveal_scope,
            requested_privacy=privacy_class,
            requested_scope=reveal_scope,
        )
        if (
            tightened_privacy != stored.privacy_class
            or tightened_scope != stored.reveal_scope
        ):
            stored = memory_ledger.update_memory(
                connection,
                memory_id=stored.id,
                actor_user_id=actor_user_id,
                privacy_class=tightened_privacy,
                reveal_scope=tightened_scope,
            )
    return result, stored


def delete_member_data(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
    actor_user_id: int,
) -> MemberMemoryDeletionResult:
    """Purge a member's subject memories and authored evidence throughout the guild ledger."""

    memory_ledger.initialize_memory_schema(connection)
    guild_id = int(guild_id)
    subject_user_id = int(subject_user_id)

    subject_memory_count = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count FROM memory_records
            WHERE guild_id = ? AND subject_user_id = ?
            """,
            (guild_id, subject_user_id),
        ).fetchone()["count"]
    )
    authored_rows = connection.execute(
        """
        SELECT receipts.id, receipts.memory_id
        FROM memory_receipts AS receipts
        JOIN memory_records AS records ON records.id = receipts.memory_id
        WHERE records.guild_id = ?
          AND records.subject_user_id != ?
          AND receipts.author_user_id = ?
        """,
        (guild_id, subject_user_id, subject_user_id),
    ).fetchall()
    authored_receipt_ids = [int(row["id"]) for row in authored_rows]
    affected_memory_ids = sorted({int(row["memory_id"]) for row in authored_rows})

    connection.execute(
        "DELETE FROM memory_records WHERE guild_id = ? AND subject_user_id = ?",
        (guild_id, subject_user_id),
    )
    if authored_receipt_ids:
        placeholders = ",".join("?" for _ in authored_receipt_ids)
        connection.execute(
            f"DELETE FROM memory_receipts WHERE id IN ({placeholders})",
            tuple(authored_receipt_ids),
        )

    orphan_memory_ids: list[int] = []
    for memory_id in affected_memory_ids:
        receipt_count = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM memory_receipts WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()["count"]
        )
        if receipt_count == 0:
            orphan_memory_ids.append(memory_id)
    for memory_id in orphan_memory_ids:
        connection.execute("DELETE FROM memory_records WHERE id = ?", (memory_id,))

    result = MemberMemoryDeletionResult(
        guild_id=guild_id,
        subject_user_id=subject_user_id,
        subject_memory_count_deleted=subject_memory_count,
        authored_cross_subject_receipt_count_deleted=len(authored_receipt_ids),
        evidence_orphan_memory_count_deleted=len(orphan_memory_ids),
    )
    audit_log.record_audit_event(
        connection,
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        action="memory.member_deleted",
        target=f"member:{subject_user_id}",
        before=None,
        after={
            "memory_count_deleted": result.memory_count_deleted,
            "subject_memory_count_deleted": result.subject_memory_count_deleted,
            "authored_cross_subject_receipt_count_deleted": result.authored_cross_subject_receipt_count_deleted,
            "evidence_orphan_memory_count_deleted": result.evidence_orphan_memory_count_deleted,
        },
    )
    return result


def delete_member_memories(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    subject_user_id: int,
    actor_user_id: int,
) -> int:
    """Compatibility wrapper returning the number of memory records removed."""

    result = delete_member_data(
        connection,
        guild_id=guild_id,
        subject_user_id=subject_user_id,
        actor_user_id=actor_user_id,
    )
    return result.memory_count_deleted
