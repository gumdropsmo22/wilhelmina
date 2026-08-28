from __future__ import annotations

from datetime import date

import pytest

from services import coven_registry, memory_context, memory_ledger, member_profiles
from services.database import initialize_database, managed_connection

TODAY = date(2026, 8, 23)


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
        _save_profile(connection, user_id=2, display_name="Founder", preferred_name="Mina")
        _register_profile(connection, user_id=3, display_name="Alex", preferred_name="Alex")
        _register_profile(connection, user_id=4, display_name="Jordan", preferred_name="Jordan")
        memory_ledger.initialize_memory_schema(connection)
    return path


def _save_profile(connection, *, user_id: int, display_name: str, preferred_name: str) -> None:
    member_profiles.save_member_identity(
        connection,
        guild_id=100,
        user_id=user_id,
        discord_display_name=display_name,
        preferred_name=preferred_name,
        birth_date="1990-10-31",
        today=TODAY,
        actor_user_id=2,
    )


def _register_profile(connection, *, user_id: int, display_name: str, preferred_name: str) -> None:
    coven_registry.register_pending_member(
        connection,
        guild_id=100,
        user_id=user_id,
        display_name=display_name,
        actor_user_id=2,
    )
    _save_profile(
        connection,
        user_id=user_id,
        display_name=display_name,
        preferred_name=preferred_name,
    )


def _add(
    connection,
    *,
    subject_user_id: int,
    summary: str,
    topic: str,
    category: str = "Interest",
    label: str = "Fact",
    privacy_class: str | None = None,
    reveal_scope: str | None = None,
    importance: int = 50,
    author_user_id: int | None = None,
    channel_id: int | None = None,
    message_id: int | None = None,
    excerpt: str | None = None,
    source_created_at: str | None = None,
):
    jump_url = (
        f"https://discord.com/channels/100/{channel_id}/{message_id}"
        if channel_id is not None and message_id is not None
        else None
    )
    return memory_ledger.add_memory(
        connection,
        guild_id=100,
        subject_user_id=subject_user_id,
        category=category,
        epistemic_label=label,
        summary=summary,
        topic_key=topic,
        actor_user_id=2,
        privacy_class=privacy_class,
        reveal_scope=reveal_scope,
        importance=importance,
        author_user_id=author_user_id,
        channel_id=channel_id,
        message_id=message_id,
        jump_url=jump_url,
        excerpt=excerpt,
        source_created_at=source_created_at,
    )


def _bundle(connection, *, query: str = "", referenced_member_ids=(), **kwargs):
    return memory_context.assemble_memory_context(
        connection,
        guild_id=100,
        interlocutor_user_id=2,
        query=query,
        on_date=TODAY,
        referenced_member_ids=referenced_member_ids,
        **kwargs,
    )


def test_full_speaker_profile_includes_owner_only_but_never_admin_only(database_path):
    with managed_connection(database_path) as connection:
        ordinary = _add(
            connection,
            subject_user_id=2,
            summary="Loves black coffee",
            topic="drink.coffee",
            category="Preference",
        )
        owner_only = _add(
            connection,
            subject_user_id=2,
            summary="Keeps a private birthday list",
            topic="birthday.private.list",
            reveal_scope="owner_only",
        )
        admin_only = _add(
            connection,
            subject_user_id=2,
            summary="Founder-only operational note",
            topic="admin.private.note",
            category="Admin note",
        )

        bundle = _bundle(connection)

    profile_ids = {item.memory.id for item in bundle.speaker_profile}
    assert ordinary.memory.id in profile_ids
    assert owner_only.memory.id in profile_ids
    assert admin_only.memory.id not in profile_ids
    assert bundle.contextual_memories == ()
    assert bundle.identity.preferred_name == "Mina"
    assert bundle.identity.birth_date == "1990-10-31"


def test_high_importance_hidden_memory_cannot_beat_low_importance_allowed_memory(database_path):
    with managed_connection(database_path) as connection:
        allowed = _add(
            connection,
            subject_user_id=3,
            summary="Collects telescope lenses",
            topic="astronomy.telescope.lenses",
            importance=1,
        )
        hidden_owner = _add(
            connection,
            subject_user_id=3,
            summary="Keeps a private telescope journal",
            topic="astronomy.telescope.private",
            reveal_scope="owner_only",
            importance=100,
        )
        hidden_admin = _add(
            connection,
            subject_user_id=3,
            summary="Admin telescope note",
            topic="astronomy.telescope.admin",
            category="Admin note",
            importance=100,
        )

        bundle = _bundle(connection, query="telescope", referenced_member_ids=(3,))

    ids = {item.memory.id for item in bundle.contextual_memories}
    assert allowed.memory.id in ids
    assert hidden_owner.memory.id not in ids
    assert hidden_admin.memory.id not in ids


def test_referenced_member_entity_retrieves_cross_member_relationship_context(database_path):
    with managed_connection(database_path) as connection:
        linked = _add(
            connection,
            subject_user_id=4,
            summary="Jordan promised Alex the vinyl box set",
            topic="relationship.alex.vinyl.promise",
            category="Relationship context",
        )
        memory_ledger.set_memory_entities(
            connection,
            memory_id=linked.memory.id,
            entities=(("member", "3"),),
        )

        bundle = _bundle(connection, referenced_member_ids=(3,))

    item = next(item for item in bundle.contextual_memories if item.memory.id == linked.memory.id)
    assert "referenced_member:3" in item.reasons


def test_referenced_subject_outranks_unrelated_fts_hit(database_path):
    with managed_connection(database_path) as connection:
        referenced = _add(
            connection,
            subject_user_id=3,
            summary="Prefers mint tea",
            topic="drink.mint.tea",
            category="Preference",
            importance=1,
        )
        unrelated = _add(
            connection,
            subject_user_id=4,
            summary="Runs a tea tasting club",
            topic="club.tea.tasting",
            importance=100,
        )

        bundle = _bundle(
            connection,
            query="tea",
            referenced_member_ids=(3,),
            contextual_limit=2,
        )

    assert bundle.contextual_memories[0].memory.id == referenced.memory.id
    assert {item.memory.id for item in bundle.contextual_memories} == {
        referenced.memory.id,
        unrelated.memory.id,
    }


def test_contradiction_expansion_adds_revealable_partner_and_filters_hidden_partner(database_path):
    with managed_connection(database_path) as connection:
        first = _add(
            connection,
            subject_user_id=3,
            summary="Sam says the project was cancelled",
            topic="project.status.claim",
            category="Gossip",
            label="Gossip",
            importance=90,
        )
        second = _add(
            connection,
            subject_user_id=3,
            summary="Lee says the project is only delayed",
            topic="project.status.claim",
            category="Gossip",
            label="Gossip",
            importance=10,
        )
        hidden = _add(
            connection,
            subject_user_id=3,
            summary="Private claim about the project status",
            topic="project.status.claim",
            category="Gossip",
            label="Gossip",
            reveal_scope="owner_only",
            importance=100,
        )

        bundle = _bundle(connection, query="project", contextual_limit=1)

    ids = {item.memory.id for item in bundle.contextual_memories}
    assert first.memory.id in ids
    assert second.memory.id in ids
    assert hidden.memory.id not in ids
    first_item = next(item for item in bundle.contextual_memories if item.memory.id == first.memory.id)
    second_item = next(item for item in bundle.contextual_memories if item.memory.id == second.memory.id)
    assert second.memory.id in first_item.contradicts_memory_ids
    assert first.memory.id in second_item.contradicts_memory_ids


def test_evidence_budget_prefers_latest_effective_excerpt_and_is_hard_bounded(database_path):
    with managed_connection(database_path) as connection:
        created = _add(
            connection,
            subject_user_id=3,
            summary="Practises opera every weekend",
            topic="music.opera.practice",
            author_user_id=3,
            channel_id=10,
            message_id=501,
            excerpt="First opera receipt with a deliberately long supporting sentence.",
            source_created_at="2026-08-20T10:00:00+00:00",
        )
        _add(
            connection,
            subject_user_id=3,
            summary="Practises opera every weekend",
            topic="music.opera.practice",
            author_user_id=3,
            channel_id=10,
            message_id=502,
            excerpt="Second opera receipt with another deliberately long supporting sentence.",
            source_created_at="2026-08-21T10:00:00+00:00",
        )
        _add(
            connection,
            subject_user_id=3,
            summary="Practises opera every weekend",
            topic="music.opera.practice",
            author_user_id=3,
            channel_id=10,
            message_id=503,
            excerpt="Third opera receipt before the edit.",
            source_created_at="2026-08-22T10:00:00+00:00",
        )
        memory_ledger.mark_message_edited(
            connection,
            guild_id=100,
            message_id=503,
            edited_excerpt="Latest edited opera evidence is authoritative for this receipt.",
            edited_at="2026-08-22T10:05:00+00:00",
        )

        bundle = _bundle(
            connection,
            query="opera",
            evidence_char_budget=35,
            evidence_per_memory=3,
        )

    item = next(item for item in bundle.contextual_memories if item.memory.id == created.memory.id)
    assert item.evidence
    assert item.evidence[0].receipt_id > 0
    assert item.evidence[0].excerpt.startswith("Latest edited opera evidence")
    assert sum(len(receipt.excerpt) for receipt in item.evidence) <= 35


def test_wrong_guild_memory_never_enters_context(database_path):
    with managed_connection(database_path) as connection:
        coven_registry.bootstrap_registry(
            connection,
            guild_id=200,
            wilhelmina_user_id=1999,
            founder_user_id=20,
            founder_name="Other Founder",
            actor_user_id=20,
        )
        memory_ledger.add_memory(
            connection,
            guild_id=200,
            subject_user_id=20,
            category="Interest",
            epistemic_label="Fact",
            summary="Obsessed with eclipse photography",
            topic_key="astronomy.eclipse.photo",
            actor_user_id=20,
        )
        local = _add(
            connection,
            subject_user_id=3,
            summary="Enjoys eclipse forecasts",
            topic="astronomy.eclipse.forecast",
        )

        bundle = _bundle(connection, query="eclipse")

    assert [item.memory.id for item in bundle.contextual_memories] == [local.memory.id]
    assert all(item.memory.guild_id == 100 for item in bundle.contextual_memories)


def test_renderer_preserves_epistemic_labels_gossip_and_identity_without_admin_leak(database_path):
    with managed_connection(database_path) as connection:
        inference = _add(
            connection,
            subject_user_id=2,
            summary="May prefer late-night planning sessions",
            topic="planning.late.night",
            category="Communication style",
            label="Inference",
            reveal_scope="owner_only",
        )
        gossip = _add(
            connection,
            subject_user_id=3,
            summary="Sam claims Alex secretly hates karaoke",
            topic="alex.karaoke.claim",
            category="Gossip",
            label="Gossip",
        )
        hidden = _add(
            connection,
            subject_user_id=3,
            summary="Admin-only karaoke note",
            topic="alex.karaoke.admin",
            category="Admin note",
        )

        bundle = _bundle(connection, query="karaoke")
        rendered = memory_context.render_memory_context_for_prompt(bundle)

    assert f"memory#{inference.memory.id}" in rendered
    assert "Inference" in rendered
    assert f"memory#{gossip.memory.id}" in rendered
    assert "Unverified gossip" in rendered
    assert "birth_date: 1990-10-31" in rendered
    assert hidden.memory.summary not in rendered


def test_missing_identity_profile_fails_before_context_retrieval(database_path):
    with managed_connection(database_path) as connection:
        coven_registry.register_pending_member(
            connection,
            guild_id=100,
            user_id=5,
            display_name="No Profile",
            actor_user_id=2,
        )
        with pytest.raises(member_profiles.MemberIdentityProfileNotFound):
            memory_context.assemble_memory_context(
                connection,
                guild_id=100,
                interlocutor_user_id=5,
                query="anything",
                on_date=TODAY,
            )


def test_non_searchable_query_still_returns_full_speaker_profile(database_path):
    with managed_connection(database_path) as connection:
        memory = _add(
            connection,
            subject_user_id=2,
            summary="Likes reaction images",
            topic="chat.reaction.images",
        )
        bundle = _bundle(connection, query="✨😂✨")

    assert {item.memory.id for item in bundle.speaker_profile} == {memory.memory.id}
    assert bundle.contextual_memories == ()
