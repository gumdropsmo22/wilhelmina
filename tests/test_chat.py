from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from services import chat, coven_registry, guild_config, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection

TODAY = date(2026, 8, 24)


def _envelope(
    *,
    guild_id: int | None = 100,
    channel_id: int = 10,
    content: str = "hello",
    author_user_id: int = 2,
    author_is_bot: bool = False,
    webhook_id: int | None = None,
    mentioned_user_ids: tuple[int, ...] = (),
    reply_author_user_id: int | None = None,
) -> chat.ChatMessageEnvelope:
    return chat.ChatMessageEnvelope(
        message_id=500,
        author_user_id=author_user_id,
        author_is_bot=author_is_bot,
        webhook_id=webhook_id,
        content=content,
        guild_id=guild_id,
        channel_id=channel_id,
        mentioned_user_ids=mentioned_user_ids,
        reply_author_user_id=reply_author_user_id,
    )


def _route(
    envelope: chat.ChatMessageEnvelope,
    *,
    designated_channel_id: int | None = 10,
) -> chat.ChatRoute:
    return chat.route_chat_message(
        envelope,
        home_guild_id=100,
        bot_user_id=999,
        designated_channel_id=designated_channel_id,
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
        for user_id, name in ((3, "Alex"), (4, "Sam")):
            coven_registry.register_pending_member(
                connection,
                guild_id=100,
                user_id=user_id,
                display_name=name,
                actor_user_id=2,
            )
            member_profiles.save_member_identity(
                connection,
                guild_id=100,
                user_id=user_id,
                discord_display_name=name,
                preferred_name=name,
                birth_date="1991-09-01",
                today=TODAY,
                actor_user_id=2,
            )
        memory_ledger.initialize_memory_schema(connection)


def _add_memory(
    connection,
    *,
    subject_user_id: int,
    summary: str,
    topic: str,
    reveal_scope: str = "cross_member",
    category: str = "Interest",
    label: str = "Fact",
):
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=subject_user_id,
        category=category,
        epistemic_label=label,
        summary=summary,
        topic_key=topic,
        actor_user_id=2,
        privacy_class="ordinary",
        reveal_scope=reveal_scope,
    ).memory


def test_dm_routes_to_private_interlocutor():
    route = _route(_envelope(guild_id=None, channel_id=77))
    assert route.eligible is True
    assert route.surface is chat.ConversationSurface.DM
    assert route.audience_scope is chat.AudienceScope.PRIVATE_INTERLOCUTOR
    assert route.guild_id == 100


def test_designated_channel_routes_to_guild_visible():
    route = _route(_envelope(channel_id=10))
    assert route.eligible is True
    assert route.surface is chat.ConversationSurface.DESIGNATED_CHANNEL
    assert route.audience_scope is chat.AudienceScope.GUILD_VISIBLE


def test_mention_and_reply_are_direct_interactions_outside_designated_channel():
    mention = _route(
        _envelope(channel_id=20, mentioned_user_ids=(999,)),
        designated_channel_id=10,
    )
    reply = _route(
        _envelope(channel_id=20, reply_author_user_id=999),
        designated_channel_id=10,
    )
    assert mention.surface is chat.ConversationSurface.MENTION
    assert reply.surface is chat.ConversationSurface.REPLY
    assert mention.audience_scope is chat.AudienceScope.GUILD_VISIBLE
    assert reply.audience_scope is chat.AudienceScope.GUILD_VISIBLE


def test_reply_and_mention_take_precedence_over_designated_surface_label():
    reply = _route(
        _envelope(
            channel_id=10,
            mentioned_user_ids=(999,),
            reply_author_user_id=999,
        )
    )
    mention = _route(_envelope(channel_id=10, mentioned_user_ids=(999,)))
    assert reply.surface is chat.ConversationSurface.REPLY
    assert mention.surface is chat.ConversationSurface.MENTION


@pytest.mark.parametrize(
    ("envelope", "reason"),
    [
        (_envelope(guild_id=200), "wrong_guild"),
        (_envelope(channel_id=20), "not_interaction"),
        (_envelope(author_is_bot=True), "non_human"),
        (_envelope(webhook_id=88), "non_human"),
        (_envelope(content="   "), "no_text"),
        (_envelope(content="  !help"), "prefix_command"),
    ],
)
def test_unapproved_or_nonhuman_messages_do_not_route(envelope, reason):
    route = _route(envelope, designated_channel_id=10)
    assert route.eligible is False
    assert route.reason == reason


def test_home_guild_is_required_even_for_dm():
    route = chat.route_chat_message(
        _envelope(guild_id=None),
        home_guild_id=None,
        bot_user_id=999,
        designated_channel_id=10,
    )
    assert route.eligible is False
    assert route.reason == "home_guild_unset"


def test_trusted_member_references_use_discord_and_registry_ids_only(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        refs = chat.resolve_referenced_member_ids(
            connection,
            guild_id=100,
            interlocutor_user_id=2,
            bot_user_id=999,
            content="Ask Alex and ⛧WTCH-0004⛧ about it, not ImaginaryName.",
            mentioned_user_ids=(3, 999, 2, 999999),
            reply_author_user_id=4,
        )

    assert refs == (3, 4)


def test_plain_language_name_does_not_become_a_member_reference(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        refs = chat.resolve_referenced_member_ids(
            connection,
            guild_id=100,
            interlocutor_user_id=2,
            bot_user_id=999,
            content="What did Alex say?",
        )

    assert refs == ()


def test_unknown_or_malformed_coven_mark_does_not_widen_retrieval(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        refs = chat.resolve_referenced_member_ids(
            connection,
            guild_id=100,
            interlocutor_user_id=2,
            bot_user_id=999,
            content="WTCH-9999 WTCH-12",
        )

    assert refs == ()


def test_local_chat_date_uses_configured_guild_timezone(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        guild_config.ensure_guild_config(connection, 100, timezone="Pacific/Kiritimati")
        instant = datetime(2026, 8, 24, 12, 30, tzinfo=timezone.utc)
        resolved = chat.local_chat_date(connection, guild_id=100, now=instant)

    assert resolved == date(2026, 8, 25)


def test_dm_keeps_speaker_owner_only_memory(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        owner_only = _add_memory(
            connection,
            subject_user_id=2,
            summary="Prefers private midnight planning",
            topic="planning.private",
            reveal_scope="owner_only",
        )
        route = _route(_envelope(guild_id=None, content="planning"))
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=route,
            interlocutor_user_id=2,
            query="planning",
            on_date=TODAY,
        )

    assert owner_only.id in {item.memory.id for item in bundle.speaker_profile}


def test_guild_visible_chat_strips_speaker_owner_only_memory(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        public = _add_memory(
            connection,
            subject_user_id=2,
            summary="Likes public astronomy debates",
            topic="astronomy.public",
        )
        owner_only = _add_memory(
            connection,
            subject_user_id=2,
            summary="Privately fears karaoke",
            topic="karaoke.private",
            reveal_scope="owner_only",
        )
        route = _route(_envelope(content="astronomy and karaoke"))
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=route,
            interlocutor_user_id=2,
            query="astronomy karaoke",
            on_date=TODAY,
        )

    speaker_ids = {item.memory.id for item in bundle.speaker_profile}
    assert public.id in speaker_ids
    assert owner_only.id not in speaker_ids


def test_guild_visible_context_keeps_other_member_cross_member_memory(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        other = _add_memory(
            connection,
            subject_user_id=3,
            summary="Alex collects antique telescopes",
            topic="astronomy.alex",
        )
        route = _route(_envelope(content="<@3> telescopes", mentioned_user_ids=(3,)))
        refs = chat.resolve_referenced_member_ids(
            connection,
            guild_id=100,
            interlocutor_user_id=2,
            bot_user_id=999,
            content="<@3> telescopes",
            mentioned_user_ids=(3,),
        )
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=route,
            interlocutor_user_id=2,
            query="telescopes",
            referenced_member_ids=refs,
            on_date=TODAY,
        )

    assert other.id in {item.memory.id for item in bundle.contextual_memories}


def test_public_filter_removes_contradiction_pointer_to_hidden_owner_only(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        public = _add_memory(
            connection,
            subject_user_id=2,
            summary="Claims karaoke is delightful",
            topic="karaoke.opinion",
            category="Gossip",
            label="Gossip",
        )
        hidden = _add_memory(
            connection,
            subject_user_id=2,
            summary="Claims karaoke is unbearable",
            topic="karaoke.opinion",
            reveal_scope="owner_only",
            category="Gossip",
            label="Gossip",
        )
        route = _route(_envelope(content="karaoke"))
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=route,
            interlocutor_user_id=2,
            query="karaoke",
            on_date=TODAY,
        )

    item = next(item for item in bundle.speaker_profile if item.memory.id == public.id)
    assert hidden.id not in {member.memory.id for member in bundle.speaker_profile}
    assert hidden.id not in item.contradicts_memory_ids


def test_collection_pause_does_not_disable_chat_context(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        memory_ledger.set_wilhelmina_channel(
            connection,
            guild_id=100,
            channel_id=10,
            actor_user_id=2,
        )
        paused = memory_ledger.set_collection_enabled(
            connection,
            guild_id=100,
            enabled=False,
            actor_user_id=2,
        )
        route = chat.route_chat_message(
            _envelope(channel_id=10),
            home_guild_id=100,
            bot_user_id=999,
            designated_channel_id=paused.wilhelmina_channel_id,
        )
        bundle = chat.assemble_chat_memory_context(
            connection,
            route=route,
            interlocutor_user_id=2,
            query="hello",
            on_date=TODAY,
        )

    assert paused.collection_enabled is False
    assert route.eligible is True
    assert bundle.interlocutor_user_id == 2


def test_ineligible_route_cannot_assemble_context(tmp_path):
    path = tmp_path / "chat.sqlite3"
    _setup(path)

    with managed_connection(path) as connection:
        with pytest.raises(chat.ChatContractError):
            chat.assemble_chat_memory_context(
                connection,
                route=chat.ChatRoute(False, reason="not_interaction"),
                interlocutor_user_id=2,
                query="hello",
                on_date=TODAY,
            )
