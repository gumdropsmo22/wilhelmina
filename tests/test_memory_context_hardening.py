from __future__ import annotations

from datetime import date

from services import coven_registry, memory_context, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection

TODAY = date(2026, 8, 23)


def _save_profile(connection, *, user_id: int, display_name: str) -> None:
    member_profiles.save_member_identity(
        connection,
        guild_id=100,
        user_id=user_id,
        discord_display_name=display_name,
        preferred_name=display_name,
        birth_date="1990-10-31",
        today=TODAY,
        actor_user_id=2,
    )


def _setup(path) -> None:
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
        _save_profile(connection, user_id=2, display_name="Founder")
        coven_registry.register_pending_member(
            connection,
            guild_id=100,
            user_id=3,
            display_name="Alex",
            actor_user_id=2,
        )
        _save_profile(connection, user_id=3, display_name="Alex")
        memory_ledger.initialize_memory_schema(connection)


def _add_memory(
    connection,
    *,
    subject_user_id: int,
    summary: str,
    topic: str = "astronomy.telescope",
    message_id: int | None = None,
    excerpt: str | None = None,
):
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=subject_user_id,
        category="Interest",
        epistemic_label="Fact",
        summary=summary,
        topic_key=topic,
        actor_user_id=2,
        reveal_scope="cross_member",
        author_user_id=subject_user_id if message_id is not None else None,
        channel_id=10 if message_id is not None else None,
        message_id=message_id,
        jump_url=(
            f"https://discord.com/channels/100/10/{message_id}"
            if message_id is not None
            else None
        ),
        excerpt=excerpt,
        source_created_at=(
            "2026-08-22T10:00:00+00:00" if message_id is not None else None
        ),
    ).memory


def _assemble(connection, *, query: str, referenced_member_ids=()):
    return memory_context.assemble_memory_context(
        connection,
        guild_id=100,
        interlocutor_user_id=2,
        query=query,
        on_date=TODAY,
        referenced_member_ids=referenced_member_ids,
    )


def test_corrupted_restricted_cross_member_row_is_excluded_from_other_member_context(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
        )
        connection.execute(
            """
            UPDATE memory_records
            SET privacy_class = 'restricted', reveal_scope = 'cross_member'
            WHERE id = ?
            """,
            (memory.id,),
        )
        bundle = _assemble(
            connection,
            query="telescope",
            referenced_member_ids=(3,),
        )

    assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_corrupted_restricted_cross_member_row_is_excluded_from_speaker_profile(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=2,
            summary="Keeps a telescope notebook",
        )
        connection.execute(
            """
            UPDATE memory_records
            SET privacy_class = 'restricted', reveal_scope = 'cross_member'
            WHERE id = ?
            """,
            (memory.id,),
        )
        bundle = _assemble(connection, query="telescope")

    assert memory.id not in {item.memory.id for item in bundle.speaker_profile}


def test_legacy_memory_summary_containing_dangerous_secret_is_excluded(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
        )
        connection.execute(
            "UPDATE memory_records SET summary = ? WHERE id = ?",
            ("auth token: abcdefgh123456", memory.id),
        )
        bundle = _assemble(
            connection,
            query="auth token",
            referenced_member_ids=(3,),
        )

    assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_legacy_memory_topic_containing_dangerous_secret_is_excluded(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
        )
        connection.execute(
            "UPDATE memory_records SET topic_key = ? WHERE id = ?",
            ("auth token: abcdefgh123456", memory.id),
        )
        bundle = _assemble(
            connection,
            query="telescope",
            referenced_member_ids=(3,),
        )

    assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_legacy_private_key_variants_are_excluded_before_context_rendering(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
        )
        for key_type in ("ENCRYPTED", "DSA"):
            connection.execute(
                "UPDATE memory_records SET summary = ? WHERE id = ?",
                (
                    f"-----BEGIN {key_type} PRIVATE KEY-----\nsecret-material\n"
                    f"-----END {key_type} PRIVATE KEY-----",
                    memory.id,
                ),
            )
            bundle = _assemble(
                connection,
                query="telescope",
                referenced_member_ids=(3,),
            )
            assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_legacy_receipt_private_key_is_omitted_from_safe_memory(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
            message_id=501,
            excerpt="I collect telescope lenses.",
        )
        connection.execute(
            "UPDATE memory_receipts SET original_excerpt = ? WHERE memory_id = ?",
            (
                "-----BEGIN DSA PRIVATE KEY-----\nsecret-material\n"
                "-----END DSA PRIVATE KEY-----",
                memory.id,
            ),
        )
        bundle = _assemble(connection, query="telescope")

    item = next(item for item in bundle.contextual_memories if item.memory.id == memory.id)
    assert item.evidence == ()


def test_corrupted_entity_guild_cannot_pull_cross_guild_memory(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        coven_registry.bootstrap_registry(
            connection,
            guild_id=200,
            wilhelmina_user_id=1999,
            founder_user_id=20,
            founder_name="Other Founder",
            actor_user_id=20,
        )
        member_profiles.save_member_identity(
            connection,
            guild_id=200,
            user_id=20,
            discord_display_name="Other Founder",
            preferred_name="Other Founder",
            birth_date="1990-10-31",
            today=TODAY,
            actor_user_id=20,
        )
        foreign_memory = memory_ledger.add_memory(
            connection,
            guild_id=200,
            subject_user_id=20,
            category="Interest",
            epistemic_label="Fact",
            summary="Other guild telescope secret",
            topic_key="astronomy.other-guild",
            actor_user_id=20,
            reveal_scope="cross_member",
        ).memory
        connection.execute(
            """
            UPDATE memory_entities
            SET guild_id = 100, entity_key = '3'
            WHERE memory_id = ? AND entity_type = 'subject'
            """,
            (foreign_memory.id,),
        )
        bundle = _assemble(
            connection,
            query="unrelated",
            referenced_member_ids=(3,),
        )

    assert foreign_memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_corrupted_receipt_guild_is_excluded_from_evidence(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
            message_id=501,
            excerpt="This receipt should not cross guilds.",
        )
        connection.execute(
            "UPDATE memory_receipts SET guild_id = 200 WHERE memory_id = ?",
            (memory.id,),
        )
        bundle = _assemble(connection, query="telescope")

    item = next(item for item in bundle.contextual_memories if item.memory.id == memory.id)
    assert item.evidence == ()


def test_legacy_receipt_secret_is_omitted_without_dropping_safe_memory(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
            message_id=501,
            excerpt="I collect telescope lenses.",
        )
        connection.execute(
            "UPDATE memory_receipts SET original_excerpt = ? WHERE memory_id = ?",
            ("auth token: abcdefgh123456", memory.id),
        )
        bundle = _assemble(connection, query="telescope")

    item = next(item for item in bundle.contextual_memories if item.memory.id == memory.id)
    assert item.evidence == ()


def test_unsafe_newer_receipt_does_not_hide_older_safe_evidence(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
            message_id=501,
            excerpt="Older safe telescope evidence.",
        )
        _add_memory(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
            message_id=502,
            excerpt="Newer safe telescope evidence before corruption.",
        )
        connection.execute(
            "UPDATE memory_receipts SET original_excerpt = ? WHERE message_id = 502",
            ("auth token: abcdefgh123456",),
        )
        bundle = _assemble(connection, query="telescope")

    item = next(item for item in bundle.contextual_memories if item.memory.id == memory.id)
    assert [receipt.excerpt for receipt in item.evidence] == ["Older safe telescope evidence."]


def test_context_fts_priority_preserves_ledger_search_order(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        first = _add_memory(
            connection,
            subject_user_id=3,
            summary="Telescope telescope telescope astronomy",
            topic="astronomy.telescope.primary",
        )
        second = _add_memory(
            connection,
            subject_user_id=3,
            summary="Owns one telescope",
            topic="astronomy.telescope.secondary",
        )
        ledger_hits = memory_ledger.search_memories(
            connection,
            guild_id=100,
            query="telescope",
            reveal_scopes=("cross_member",),
        )
        bundle = _assemble(connection, query="telescope")

    ledger_ids = [hit.memory.id for hit in ledger_hits if hit.memory.id in {first.id, second.id}]
    context_ids = [
        item.memory.id
        for item in bundle.contextual_memories
        if item.memory.id in {first.id, second.id}
    ]
    assert context_ids == ledger_ids
