from __future__ import annotations

from datetime import date

from services import coven_registry, memory_context, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection

TODAY = date(2026, 8, 24)


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
        member_profiles.save_member_identity(
            connection,
            guild_id=100,
            user_id=2,
            discord_display_name="Founder",
            preferred_name="Founder",
            birth_date="1990-10-31",
            today=TODAY,
            actor_user_id=2,
        )
        coven_registry.register_pending_member(
            connection,
            guild_id=100,
            user_id=3,
            display_name="Alex",
            actor_user_id=2,
        )
        member_profiles.save_member_identity(
            connection,
            guild_id=100,
            user_id=3,
            discord_display_name="Alex",
            preferred_name="Alex",
            birth_date="1991-09-01",
            today=TODAY,
            actor_user_id=2,
        )
        memory_ledger.initialize_memory_schema(connection)


def _add_memory(
    connection,
    *,
    subject_user_id: int,
    message_id: int | None = None,
):
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=subject_user_id,
        category="Interest",
        epistemic_label="Fact",
        summary="Collects telescope lenses",
        topic_key="astronomy.telescope",
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
        excerpt="Safe telescope evidence." if message_id is not None else None,
        source_created_at=(
            "2026-08-24T08:00:00+00:00" if message_id is not None else None
        ),
    ).memory


def _assemble(connection):
    return memory_context.assemble_memory_context(
        connection,
        guild_id=100,
        interlocutor_user_id=2,
        query="telescope",
        on_date=TODAY,
        referenced_member_ids=(3,),
    )


def test_openpgp_private_key_memory_is_excluded(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(connection, subject_user_id=3)
        connection.execute(
            "UPDATE memory_records SET summary = ? WHERE id = ?",
            (
                "-----BEGIN PGP PRIVATE KEY BLOCK-----\nsecret-material\n"
                "-----END PGP PRIVATE KEY BLOCK-----",
                memory.id,
            ),
        )
        bundle = _assemble(connection)

    assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_openpgp_private_key_receipt_is_excluded(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(connection, subject_user_id=3, message_id=700)
        connection.execute(
            "UPDATE memory_receipts SET original_excerpt = ? WHERE memory_id = ?",
            (
                "-----BEGIN PGP PRIVATE KEY BLOCK-----\nsecret-material\n"
                "-----END PGP PRIVATE KEY BLOCK-----",
                memory.id,
            ),
        )
        bundle = _assemble(connection)

    item = next(item for item in bundle.contextual_memories if item.memory.id == memory.id)
    assert item.evidence == ()


def test_putty_private_key_memory_is_excluded(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(connection, subject_user_id=3)
        connection.execute(
            "UPDATE memory_records SET summary = ? WHERE id = ?",
            (
                "PuTTY-User-Key-File-3: ssh-rsa\nEncryption: aes256-cbc\n"
                "Private-Lines: 1\nsecret-material",
                memory.id,
            ),
        )
        bundle = _assemble(connection)

    assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_ssh2_private_key_memory_is_excluded(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(connection, subject_user_id=3)
        connection.execute(
            "UPDATE memory_records SET summary = ? WHERE id = ?",
            (
                "---- BEGIN SSH2 ENCRYPTED PRIVATE KEY ----\nsecret-material\n"
                "---- END SSH2 ENCRYPTED PRIVATE KEY ----",
                memory.id,
            ),
        )
        bundle = _assemble(connection)

    assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_non_pem_private_key_receipts_are_excluded(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(connection, subject_user_id=3, message_id=701)
        for secret in (
            "PuTTY-User-Key-File-2: ssh-rsa\nPrivate-Lines: 1\nsecret-material",
            "---- BEGIN SSH2 PRIVATE KEY ----\nsecret-material\n---- END SSH2 PRIVATE KEY ----",
        ):
            connection.execute(
                "UPDATE memory_receipts SET original_excerpt = ? WHERE memory_id = ?",
                (secret, memory.id),
            )
            bundle = _assemble(connection)
            item = next(
                item for item in bundle.contextual_memories if item.memory.id == memory.id
            )
            assert item.evidence == ()


def test_corrupted_admin_note_cross_member_is_excluded_from_other_member_context(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(connection, subject_user_id=3)
        connection.execute(
            """
            UPDATE memory_records
            SET category = 'Admin note', privacy_class = 'ordinary', reveal_scope = 'cross_member'
            WHERE id = ?
            """,
            (memory.id,),
        )
        bundle = _assemble(connection)

    assert memory.id not in {item.memory.id for item in bundle.contextual_memories}


def test_corrupted_admin_note_cross_member_is_excluded_from_speaker_profile(tmp_path):
    path = tmp_path / "context.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory = _add_memory(connection, subject_user_id=2)
        connection.execute(
            """
            UPDATE memory_records
            SET category = 'Admin note', privacy_class = 'ordinary', reveal_scope = 'cross_member'
            WHERE id = ?
            """,
            (memory.id,),
        )
        bundle = _assemble(connection)

    assert memory.id not in {item.memory.id for item in bundle.speaker_profile}
