from __future__ import annotations

import sqlite3

from services import memory_extraction, memory_ledger


def _source_receipts(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    message_id: int,
) -> list[sqlite3.Row]:
    memory_ledger.initialize_memory_schema(connection)
    return connection.execute(
        """
        SELECT * FROM memory_receipts
        WHERE guild_id = ? AND message_id = ? AND source_kind = 'discord'
        ORDER BY id ASC
        """,
        (int(guild_id), int(message_id)),
    ).fetchall()


def _preserve_edit_history(
    connection: sqlite3.Connection,
    *,
    receipt_id: int,
    original_excerpt: str,
    edited_excerpt: str,
    edited_at: str,
) -> None:
    connection.execute(
        """
        UPDATE memory_receipts
        SET original_excerpt = ?, edited_excerpt = ?, source_edited_at = ?
        WHERE id = ?
        """,
        (original_excerpt, edited_excerpt, edited_at, int(receipt_id)),
    )


def apply_proposal(
    connection: sqlite3.Connection,
    *,
    job: memory_extraction.ExtractionJob,
    proposal: memory_extraction.MemoryProposal,
    actor_user_id: int,
) -> memory_extraction.ApplyResult:
    """Apply typed proposals while preserving message-edit evidence history."""

    memory_extraction.initialize_extraction_schema(connection)
    if not job.content:
        raise memory_extraction.ExtractionError("claimed extraction job has no content")

    previous_receipts = _source_receipts(
        connection,
        guild_id=job.guild_id,
        message_id=job.message_id,
    )
    previous_memory_ids = {int(row["memory_id"]) for row in previous_receipts}
    original_excerpt = (
        str(previous_receipts[0]["original_excerpt"])
        if previous_receipts
        else job.content
    )
    touched: set[int] = set()

    for candidate in proposal.candidates:
        if candidate.confidence < memory_extraction.MIN_CONFIDENCE:
            continue
        result = memory_ledger.add_memory(
            connection,
            guild_id=job.guild_id,
            subject_user_id=job.subject_user_id,
            category=candidate.category,
            epistemic_label=candidate.epistemic_label,
            summary=candidate.summary,
            actor_user_id=actor_user_id,
            topic_key=candidate.topic_key,
            author_user_id=job.author_user_id,
            channel_id=job.channel_id,
            message_id=job.message_id,
            jump_url=job.jump_url,
            excerpt=job.content,
            source_created_at=job.source_created_at,
            source_context=job.source_context,
            privacy_class="ordinary",
            reveal_scope="cross_member",
            importance=candidate.importance,
        )
        touched.add(result.memory.id)
        if job.source_edited_at:
            _preserve_edit_history(
                connection,
                receipt_id=result.receipt.id,
                original_excerpt=original_excerpt,
                edited_excerpt=job.content,
                edited_at=job.source_edited_at,
            )
        memory_ledger.set_memory_entities(
            connection,
            memory_id=result.memory.id,
            entities=[
                (entity.entity_type, entity.entity_key)
                for entity in candidate.entities
            ],
        )

    removed_receipts = 0
    deleted_orphans = 0
    for memory_id in sorted(previous_memory_ids - touched):
        # The canonical Ledger API may already have removed this record as part of a
        # same-topic correction. In that case its dependent receipt disappeared via
        # cascade and reconciliation has nothing left to clean up.
        existing = memory_ledger.get_memory(connection, memory_id, required=False)
        if existing is None:
            continue

        cursor = connection.execute(
            """
            DELETE FROM memory_receipts
            WHERE memory_id = ? AND guild_id = ? AND message_id = ? AND source_kind = 'discord'
            """,
            (int(memory_id), int(job.guild_id), int(job.message_id)),
        )
        removed_receipts += int(cursor.rowcount)
        remaining = connection.execute(
            "SELECT COUNT(*) AS count FROM memory_receipts WHERE memory_id = ?",
            (int(memory_id),),
        ).fetchone()
        if remaining is not None and int(remaining["count"]) == 0:
            memory_ledger.delete_memory(
                connection,
                memory_id=memory_id,
                actor_user_id=actor_user_id,
            )
            deleted_orphans += 1

    return memory_extraction.ApplyResult(
        tuple(sorted(touched)),
        removed_receipts,
        deleted_orphans,
    )
