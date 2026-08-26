from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services import coven_registry, guild_config, memory_context

COVEN_MARK_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:⛧)?WTCH-\d{4,}(?:⛧)?(?![A-Z0-9])",
    re.IGNORECASE,
)


class ChatContractError(ValueError):
    """Raised when a trusted chat-routing request is structurally invalid."""


class ConversationSurface(str, Enum):
    """Approved direct-interaction surfaces for Phase 6 chat."""

    DM = "dm"
    DESIGNATED_CHANNEL = "designated_channel"
    MENTION = "mention"
    REPLY = "reply"


class AudienceScope(str, Enum):
    """Who can read the eventual Discord response."""

    PRIVATE_INTERLOCUTOR = "private_interlocutor"
    GUILD_VISIBLE = "guild_visible"


@dataclass(frozen=True)
class ChatMessageEnvelope:
    """Discord-derived facts used by deterministic chat routing."""

    message_id: int
    author_user_id: int
    author_is_bot: bool
    webhook_id: int | None
    content: str
    guild_id: int | None
    channel_id: int
    mentioned_user_ids: tuple[int, ...] = ()
    reply_author_user_id: int | None = None


@dataclass(frozen=True)
class ChatRoute:
    """Deterministic routing decision made before memory retrieval."""

    eligible: bool
    guild_id: int | None = None
    surface: ConversationSurface | None = None
    audience_scope: AudienceScope | None = None
    reason: str = ""


def route_chat_message(
    envelope: ChatMessageEnvelope,
    *,
    home_guild_id: int | None,
    bot_user_id: int,
    designated_channel_id: int | None,
    command_prefix: str = "!",
) -> ChatRoute:
    """Classify one message without widening the approved interaction scope."""

    if envelope.author_is_bot or envelope.webhook_id is not None:
        return ChatRoute(False, reason="non_human")

    content = str(envelope.content or "")
    if not content.strip():
        return ChatRoute(False, reason="no_text")
    if command_prefix and content.lstrip().startswith(command_prefix):
        return ChatRoute(False, reason="prefix_command")
    if home_guild_id is None:
        return ChatRoute(False, reason="home_guild_unset")

    resolved_home_guild_id = int(home_guild_id)
    if envelope.guild_id is None:
        return ChatRoute(
            True,
            guild_id=resolved_home_guild_id,
            surface=ConversationSurface.DM,
            audience_scope=AudienceScope.PRIVATE_INTERLOCUTOR,
            reason="dm",
        )

    if int(envelope.guild_id) != resolved_home_guild_id:
        return ChatRoute(False, reason="wrong_guild")

    if envelope.reply_author_user_id == int(bot_user_id):
        return ChatRoute(
            True,
            guild_id=resolved_home_guild_id,
            surface=ConversationSurface.REPLY,
            audience_scope=AudienceScope.GUILD_VISIBLE,
            reason="reply",
        )

    if int(bot_user_id) in {int(value) for value in envelope.mentioned_user_ids}:
        return ChatRoute(
            True,
            guild_id=resolved_home_guild_id,
            surface=ConversationSurface.MENTION,
            audience_scope=AudienceScope.GUILD_VISIBLE,
            reason="mention",
        )

    if (
        designated_channel_id is not None
        and int(envelope.channel_id) == int(designated_channel_id)
    ):
        return ChatRoute(
            True,
            guild_id=resolved_home_guild_id,
            surface=ConversationSurface.DESIGNATED_CHANNEL,
            audience_scope=AudienceScope.GUILD_VISIBLE,
            reason="designated_channel",
        )

    return ChatRoute(False, reason="not_interaction")


def _append_registry_member(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    user_id: int,
    interlocutor_user_id: int,
    bot_user_id: int,
    resolved: list[int],
    seen: set[int],
) -> None:
    candidate_id = int(user_id)
    if candidate_id <= 0 or candidate_id in seen:
        return
    if candidate_id in {int(interlocutor_user_id), int(bot_user_id)}:
        return

    entry = coven_registry.get_entry(
        connection,
        guild_id=guild_id,
        user_id=candidate_id,
        required=False,
    )
    if entry is None or entry.is_system:
        return

    seen.add(candidate_id)
    resolved.append(candidate_id)


def resolve_referenced_member_ids(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    interlocutor_user_id: int,
    bot_user_id: int,
    content: str,
    mentioned_user_ids: tuple[int, ...] = (),
    reply_author_user_id: int | None = None,
) -> tuple[int, ...]:
    """Resolve only Discord- or Registry-authenticated member references.

    Natural-language names are intentionally not resolved here. A future model may not
    invent member IDs or use fuzzy name matching to widen memory retrieval authority.
    """

    resolved: list[int] = []
    seen: set[int] = set()
    max_members = memory_context.MAX_REFERENCED_MEMBERS

    for user_id in mentioned_user_ids:
        _append_registry_member(
            connection,
            guild_id=guild_id,
            user_id=user_id,
            interlocutor_user_id=interlocutor_user_id,
            bot_user_id=bot_user_id,
            resolved=resolved,
            seen=seen,
        )
        if len(resolved) >= max_members:
            return tuple(resolved)

    if reply_author_user_id is not None:
        _append_registry_member(
            connection,
            guild_id=guild_id,
            user_id=reply_author_user_id,
            interlocutor_user_id=interlocutor_user_id,
            bot_user_id=bot_user_id,
            resolved=resolved,
            seen=seen,
        )
        if len(resolved) >= max_members:
            return tuple(resolved)

    for match in COVEN_MARK_PATTERN.finditer(str(content or "")):
        try:
            entry = coven_registry.get_entry_by_mark(
                connection,
                guild_id=guild_id,
                mark=match.group(0),
            )
        except coven_registry.RegistryError:
            continue
        _append_registry_member(
            connection,
            guild_id=guild_id,
            user_id=entry.user_id,
            interlocutor_user_id=interlocutor_user_id,
            bot_user_id=bot_user_id,
            resolved=resolved,
            seen=seen,
        )
        if len(resolved) >= max_members:
            break

    return tuple(resolved)


def local_chat_date(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    now: datetime | None = None,
) -> date:
    """Return the guild-local date used for trusted age/birthday context."""

    config = guild_config.get_guild_config(connection, guild_id)
    timezone_name = config.timezone if config is not None else guild_config.DEFAULT_TIMEZONE
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo(guild_config.DEFAULT_TIMEZONE)

    instant = now if now is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(zone).date()


def _guild_visible_evidence_allowed(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    receipt_id: int,
) -> bool:
    """Authorize raw receipt evidence independently from its attached memory record.

    A cross-member summary can be safe to use publicly while its raw source message is not.
    Guild-visible prompts therefore use receipt text only when the receipt came from a guild
    message and that exact Discord source is not also evidence for any non-cross-member,
    restricted, or Admin-note memory. This prevents one multi-memory source message from
    smuggling owner/admin-only text through a surviving public memory.
    """

    receipt = connection.execute(
        """
        SELECT id, guild_id, source_kind, source_context, message_id
        FROM memory_receipts
        WHERE id = ? AND guild_id = ?
        """,
        (int(receipt_id), int(guild_id)),
    ).fetchone()
    if receipt is None:
        return False
    if str(receipt["source_kind"]) != "discord" or str(receipt["source_context"]) != "guild":
        return False
    if receipt["message_id"] is None:
        return False

    hidden_sibling = connection.execute(
        """
        SELECT 1
        FROM memory_receipts AS sibling
        JOIN memory_records AS sibling_memory ON sibling_memory.id = sibling.memory_id
        WHERE sibling.guild_id = ?
          AND sibling.source_kind = 'discord'
          AND sibling.source_context = ?
          AND sibling.message_id = ?
          AND (
              sibling_memory.reveal_scope != 'cross_member'
              OR sibling_memory.privacy_class = 'restricted'
              OR sibling_memory.category = 'Admin note'
          )
        LIMIT 1
        """,
        (
            int(guild_id),
            str(receipt["source_context"]),
            int(receipt["message_id"]),
        ),
    ).fetchone()
    return hidden_sibling is None


def _filter_bundle_for_audience(
    connection: sqlite3.Connection,
    bundle: memory_context.MemoryContextBundle,
    *,
    audience_scope: AudienceScope,
) -> memory_context.MemoryContextBundle:
    """Apply Discord-audience reveal rules after Phase-5 authorization."""

    if audience_scope is AudienceScope.PRIVATE_INTERLOCUTOR:
        speaker_profile = tuple(
            item
            for item in bundle.speaker_profile
            if item.memory.reveal_scope in {"cross_member", "owner_only"}
        )
    elif audience_scope is AudienceScope.GUILD_VISIBLE:
        speaker_profile = tuple(
            item
            for item in bundle.speaker_profile
            if item.memory.reveal_scope == "cross_member"
        )
    else:  # pragma: no cover - Enum exhaustiveness defence
        raise ChatContractError(f"Unsupported audience scope: {audience_scope!r}")

    contextual_memories = tuple(
        item
        for item in bundle.contextual_memories
        if item.memory.reveal_scope == "cross_member"
    )
    included_ids = {
        item.memory.id for item in (*speaker_profile, *contextual_memories)
    }

    def trim_item(item: memory_context.ContextMemory) -> memory_context.ContextMemory:
        evidence = item.evidence
        if audience_scope is AudienceScope.GUILD_VISIBLE:
            evidence = tuple(
                receipt
                for receipt in evidence
                if _guild_visible_evidence_allowed(
                    connection,
                    guild_id=bundle.guild_id,
                    receipt_id=receipt.receipt_id,
                )
            )
        return replace(
            item,
            evidence=evidence,
            contradicts_memory_ids=tuple(
                memory_id
                for memory_id in item.contradicts_memory_ids
                if memory_id in included_ids
            ),
        )

    return replace(
        bundle,
        speaker_profile=tuple(trim_item(item) for item in speaker_profile),
        contextual_memories=tuple(trim_item(item) for item in contextual_memories),
    )


def assemble_chat_memory_context(
    connection: sqlite3.Connection,
    *,
    route: ChatRoute,
    interlocutor_user_id: int,
    query: str,
    referenced_member_ids: tuple[int, ...] = (),
    on_date: date | None = None,
) -> memory_context.MemoryContextBundle:
    """Assemble Phase-5 memory context and enforce the Phase-6 audience boundary."""

    if not route.eligible or route.guild_id is None or route.audience_scope is None:
        raise ChatContractError("Chat route must be eligible before context assembly")

    resolved_date = on_date or local_chat_date(connection, guild_id=route.guild_id)
    bundle = memory_context.assemble_memory_context(
        connection,
        guild_id=route.guild_id,
        interlocutor_user_id=interlocutor_user_id,
        query=query,
        on_date=resolved_date,
        referenced_member_ids=referenced_member_ids,
    )
    return _filter_bundle_for_audience(
        connection,
        bundle,
        audience_scope=route.audience_scope,
    )
