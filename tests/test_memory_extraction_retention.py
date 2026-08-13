from __future__ import annotations

import pytest

from services import coven_registry, memory_extraction, memory_extraction_retention
from services.database import initialize_database, managed_connection


@pytest.fixture()
def database_path(tmp_path):
    path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(path)
    with managed_connection(path) as connection:
        coven_registry.bootstrap_registry(
            connection,
            guild_id=100,
            wilhelmina_user_id=999,
            founder_user_id=2,
            founder_name="Founder",
            actor_user_id=2,
        )
        memory_extraction.initialize_extraction_schema(connection)
    return path


def _enqueue(connection):
    return memory_extraction.enqueue_message(
        connection,
        guild_id=100,
        subject_user_id=2,
        source_context="guild",
        author_user_id=2,
        channel_id=10,
        message_id=500,
        jump_url="https://discord.com/channels/100/10/500",
        content="I prefer tea",
        source_created_at="2026-08-13T10:00:00+00:00",
    )


def test_retry_bookkeeping_does_not_extend_absolute_raw_text_ttl(database_path):
    with managed_connection(database_path) as connection:
        queued = _enqueue(connection)
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET created_at = '2000-01-01T00:00:00+00:00',
                updated_at = '2999-01-01T00:00:00+00:00',
                status = 'retry',
                available_at = '2999-01-01T00:00:00+00:00'
            WHERE id = ?
            """,
            (queued.id,),
        )
        expired = memory_extraction_retention.expire_transient_source_text(connection)
        current = memory_extraction.get_job(connection, queued.id)

    assert expired == 1
    assert current is not None
    assert current.status == "rejected"
    assert current.content is None
    assert current.last_error_code == "queue_expired"


def test_real_source_edit_resets_absolute_raw_text_ttl(database_path):
    with managed_connection(database_path) as connection:
        queued = _enqueue(connection)
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET created_at = '2000-01-01T00:00:00+00:00',
                updated_at = '2000-01-01T00:00:00+00:00',
                source_edited_at = '2999-01-01T00:00:00+00:00'
            WHERE id = ?
            """,
            (queued.id,),
        )
        expired = memory_extraction_retention.expire_transient_source_text(connection)
        current = memory_extraction.get_job(connection, queued.id)

    assert expired == 0
    assert current is not None
    assert current.status == "pending"
    assert current.content == "I prefer tea"
