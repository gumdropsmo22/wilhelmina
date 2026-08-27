from __future__ import annotations

from datetime import date

import pytest

from services import chat, coven_registry, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection

TODAY = date(2026, 8, 26)


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
            preferred_name="Mina",
            birth_date="1990-10-31",
            today=TODAY,
            actor_user_id=2,
        )
        memory_ledger.initialize_memory_schema(connection)


def _guild_route() -> chat.ChatRoute:
    return chat.ChatRoute(
        eligible=True,
        guild_id=100,
        surface=chat.ConversationSurface.DESIGNATED_CHANNEL,
        audience_scope=chat.AudienceScope.GUILD_VISIBLE,
        reason="test",
    )


def _dm_route() -> chat.ChatRoute:
    return chat.ChatRoute(
        eligible=True,
        guild_id=100,
        surface=chat.ConversationSurface.DM,
        audience_scope=chat.AudienceScope.PRIVATE_INTERLOCUTOR,
        reason="test",
    )


def _add_discord_memory(
    connection,
    *,
    summary: str,
    topic: str,
    message_id: int,
    excerpt: str,
    reveal_scope: str = "cross_member",
    source_context: str = "guild",
    subject_user_id: int = 2,
    author_user_id: int | None = None,
):
    guild_source = source_context == "guild"
    author_id = subject_user_id if author_user_id is None else author_user_id
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=subject_user_id,
        category="Interest",
        epistemic_label="Fact",
        summary=summary,
        topic_key=topic,
        actor_user_id=2,
        author_user_id=author_id,
        channel_id=10 if guild_source else None,
        message_id=message_id,
        jump_url=(
            f"https://discord.com/channels/100/10/{message_id}" if guild_source else None
        ),
        excerpt=excerpt,
        source_created_at="2026-08-26T00:00:00+00:00",
        source_context=source_context,
        privacy_class="ordinary",
        reveal_scope=reveal_scope,
    ).memory


@pytest.mark.parametrize("hidden_scope", ["owner_only", "admin_only"])
def test_guild_visible_receipt_is_removed_when_same_source_backs_hidden_memory(
    tmp_path,
    hidden_scope,
):
    path = tmp_path / "chat.sqlite3"
    _setup(path)
    shared_excerpt = "I love astronomy, and privately I am terrified of karaoke."

    with managed_connection(path) as connection:
        public = _add_discord_memory(
            connection,
            summary="Loves astronomy",
            topic="astronomy.public",
            message_id=700,
            excerpt=shared_excerpt,
        )
        hidden = _add_discord_memory(
            connection,
            summary="Is terrified of karaoke",
            topic="karaoke.private",
            message_id=700,
            excerpt=shared_excerpt,
            reveal_scope=hidden_scope,
        )
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=_guild_route(),
            interlocutor_user_id=2,
            query="astronomy karaoke",
            on_date=TODAY,
        )

    public_item = next(item for item in bundle.speaker_profile if item.memory.id == public.id)
    assert hidden.id not in {item.memory.id for item in bundle.speaker_profile}
    assert public_item.evidence == ()


def test_guild_visible_receipt_keeps_clean_guild_source_evidence(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        public = _add_discord_memory(
            connection,
            summary="Loves astronomy",
            topic="astronomy.public",
            message_id=701,
            excerpt="I love astronomy and antique telescopes.",
        )
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=_guild_route(),
            interlocutor_user_id=2,
            query="astronomy telescopes",
            on_date=TODAY,
        )

    public_item = next(item for item in bundle.speaker_profile if item.memory.id == public.id)
    assert len(public_item.evidence) == 1
    assert "antique telescopes" in public_item.evidence[0].excerpt


def test_guild_visible_prompt_never_uses_raw_dm_receipt_text(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        public = _add_discord_memory(
            connection,
            summary="Likes astronomy",
            topic="astronomy.dm",
            message_id=702,
            excerpt="This raw DM contains extra private phrasing beyond the saved summary.",
            source_context="dm",
        )
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=_guild_route(),
            interlocutor_user_id=2,
            query="astronomy",
            on_date=TODAY,
        )

    public_item = next(item for item in bundle.speaker_profile if item.memory.id == public.id)
    assert public_item.evidence == ()


def test_private_dm_drops_other_members_raw_dm_receipt_text(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)
    shared_excerpt = "I like astronomy, and privately I am terrified of karaoke."

    with managed_connection(path) as connection:
        coven_registry.register_pending_member(
            connection,
            guild_id=100,
            user_id=3,
            display_name="Other",
            actor_user_id=2,
        )
        member_profiles.save_member_identity(
            connection,
            guild_id=100,
            user_id=3,
            discord_display_name="Other",
            preferred_name="Other",
            birth_date="1991-01-02",
            today=TODAY,
            actor_user_id=2,
        )
        public = _add_discord_memory(
            connection,
            subject_user_id=3,
            author_user_id=3,
            summary="Likes astronomy",
            topic="other.astronomy",
            message_id=800,
            excerpt=shared_excerpt,
            source_context="dm",
        )
        hidden = _add_discord_memory(
            connection,
            subject_user_id=3,
            author_user_id=3,
            summary="Is terrified of karaoke",
            topic="other.karaoke.private",
            message_id=800,
            excerpt=shared_excerpt,
            source_context="dm",
            reveal_scope="owner_only",
        )
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=_dm_route(),
            interlocutor_user_id=2,
            query="astronomy karaoke",
            referenced_member_ids=(3,),
            on_date=TODAY,
        )

    contextual_ids = {item.memory.id for item in bundle.contextual_memories}
    assert public.id in contextual_ids
    assert hidden.id not in contextual_ids
    public_item = next(item for item in bundle.contextual_memories if item.memory.id == public.id)
    assert public_item.evidence == ()
