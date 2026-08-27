from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from services import memory_extraction
from services.database import utc_now_iso


def expire_transient_source_text(
    connection: sqlite3.Connection,
    *,
    ttl_seconds: int = memory_extraction.QUEUE_CONTENT_TTL_SECONDS,
) -> int:
    """Erase outstanding source text after an absolute queue/edit age threshold.

    Retry bookkeeping and provider processing must not extend the retention window. Initial
    messages age from the queue row's creation time; edited messages age from the source edit
    timestamp. Expiring a processing row also revokes its claim token so a late provider result
    cannot mutate the Memory Ledger.
    """

    memory_extraction.initialize_extraction_schema(connection)
    cutoff = (datetime.now(UTC) - timedelta(seconds=int(ttl_seconds))).isoformat(
        timespec="seconds"
    )
    cursor = connection.execute(
        """
        UPDATE memory_extraction_jobs
        SET status = 'rejected', content = NULL, lease_expires_at = NULL,
            claim_token = NULL, last_error_code = 'queue_expired', updated_at = ?
        WHERE status IN ('pending', 'processing', 'retry')
          AND content IS NOT NULL
          AND COALESCE(source_edited_at, created_at) <= ?
        """,
        (utc_now_iso(), cutoff),
    )
    return int(cursor.rowcount)
