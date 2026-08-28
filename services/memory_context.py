from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Sequence

from services import memory_extraction, memory_ledger, member_profiles
from services.member_identity import TrustedIdentityContext

DEFAULT_CONTEXTUAL_LIMIT = 18
MAX_CONTEXTUAL_LIMIT = 50
DEFAULT_EVIDENCE_CHAR_BUDGET = 16_000
MAX_EVIDENCE_CHAR_BUDGET = 50_000
DEFAULT_EVIDENCE_PER_MEMORY = 2
MAX_EVIDENCE_PER_MEMORY = 5
MAX_EVIDENCE_EXCERPT_CHARS = 1_200
MAX_REFERENCED_MEMBERS = 16
MAX_CONTRADICTION_PARTNERS_PER_MEMORY = 2

REFERENCED_SUBJECT_WEIGHT = 500.0
REFERENCED_MEMBER_WEIGHT = 425.0
FTS_TOP_WEIGHT = 300.0
PRIVATE_KEY_PATTERNS = (
    re.compile(
        r"-----BEGIN(?: [A-Z0-9-]+)* PRIVATE KEY(?: BLOCK)?-----",
        re.IGNORECASE,
    ),
    re.compile(r"^PuTTY-User-Key-File-\d+:\s*\S+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"---- BEGIN SSH2(?: ENCRYPTED)? PRIVATE KEY ----", re.IGNORECASE),
)


class MemoryContextError(ValueError):
    """Raised when a trusted context request is structurally invalid."""


@dataclass(frozen=True)
class ContextEvidence:
    receipt_id: int
    memory_id: int
    source_kind: str
    source_context: str
    author_user_id: int
    excerpt: str
    source_created_at: str
    source_edited_at: str | None
    source_deleted_at: str | None


@dataclass(frozen=True)
class ContextMemory:
    memory: memory_ledger.MemoryRecord
    relevance_score: float
    reasons: tuple[str, ...]
    evidence: tuple[ContextEvidence, ...]
    contradicts_memory_ids: tuple[int, ...]


@dataclass(frozen=True)
class MemoryContextBundle:
    guild_id: int
    interlocutor_user_id: int
    identity: TrustedIdentityContext
    speaker_profile: tuple[ContextMemory, ...]
    contextual_memories: tuple[ContextMemory, ...]


@dataclass
class _Candidate:
    memory: memory_ledger.MemoryRecord
    score: float
    reasons: set[str] = field(default_factory=set)


def _bounded_int(value: int, *, minimum: int, maximum: int, field_name: str) -> int:
    resolved = int(value)
    if resolved < minimum:
        raise MemoryContextError(f"{field_name} must be at least {minimum}")
    return min(resolved, maximum)


def _normalize_referenced_member_ids(
    member_ids: Sequence[int],
    *,
    interlocutor_user_id: int,
) -> tuple[int, ...]:
    resolved: list[int] = []
    seen: set[int] = set()
    for raw_value in member_ids:
        value = int(raw_value)
        if value <= 0:
            raise MemoryContextError("referenced member IDs must be positive integers")
        if value == int(interlocutor_user_id) or value in seen:
            continue
        seen.add(value)
        resolved.append(value)
        if len(resolved) >= MAX_REFERENCED_MEMBERS:
            break
    return tuple(resolved)


def _content_is_safe(value: str) -> bool:
    """Keep legacy dangerous-secret content out of future chat context."""

    if any(pattern.search(value) for pattern in PRIVATE_KEY_PATTERNS):
        return False
    try:
        memory_extraction.guard_extractable_text(value)
    except memory_ledger.MemoryLedgerError:
        return False
    return True


def _memory_is_context_revealable(
    memory: memory_ledger.MemoryRecord,
    *,
    interlocutor_user_id: int,
) -> bool:
    # The service layer defines restricted + cross_member as invalid even though the
    # SQLite columns have independent CHECK constraints. Fail closed if a legacy,
    # manually-edited, or corrupted row ever reaches that impossible combination.
    if memory.privacy_class == "restricted" and memory.reveal_scope == "cross_member":
        return False
    # Admin notes are canonical restricted/admin-only records. Recheck the category
    # invariant here so manually repaired/imported rows cannot become chat-revealable.
    if memory.category == "Admin note" and (
        memory.privacy_class != "restricted" or memory.reveal_scope != "admin_only"
    ):
        return False
    if not _content_is_safe(memory.summary) or not _content_is_safe(memory.topic_key):
        return False
    return memory_ledger.memory_is_revealable(
        memory,
        interlocutor_user_id=interlocutor_user_id,
        allow_admin=False,
    )


def _add_candidate(
    candidates: dict[int, _Candidate],
    memory: memory_ledger.MemoryRecord,
    *,
    reason: str,
    weight: float,
) -> None:
    candidate = candidates.get(memory.id)
    if candidate is None:
        candidate = _Candidate(memory=memory, score=float(memory.importance))
        candidates[memory.id] = candidate
    if reason in candidate.reasons:
        return
    candidate.reasons.add(reason)
    candidate.score += float(weight)


def _candidate_sort_key(candidate: _Candidate) -> tuple[float, int, str, int]:
    return (
        candidate.score,
        candidate.memory.importance,
        candidate.memory.updated_at,
        candidate.memory.id,
    )


def _safe_search_query(query: str) -> str:
    return " ".join(str(query or "").split())[:500]


def _authorized_cross_member_candidates(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    interlocutor_user_id: int,
    query: str,
    referenced_member_ids: Sequence[int],
    contextual_limit: int,
) -> dict[int, _Candidate]:
    """Collect only already-authorized cross-member rows before ranking them."""

    candidates: dict[int, _Candidate] = {}
    fetch_limit = min(100, max(20, contextual_limit * 4))
    search_query = _safe_search_query(query)

    if search_query:
        try:
            hits = memory_ledger.search_memories(
                connection,
                guild_id=guild_id,
                query=search_query,
                reveal_scopes=("cross_member",),
                limit=fetch_limit,
            )
        except memory_ledger.MemoryLedgerError:
            hits = []
        # search_memories already orders SQLite bm25 smaller-is-better. Convert that
        # ordering to a deterministic descending weight rather than reinterpreting the
        # provider-specific rank number (which may be negative and extremely small).
        for index, hit in enumerate(hits):
            memory = hit.memory
            if memory.subject_user_id == int(interlocutor_user_id):
                continue
            if not _memory_is_context_revealable(
                memory,
                interlocutor_user_id=interlocutor_user_id,
            ):
                continue
            _add_candidate(
                candidates,
                memory,
                reason="fts",
                weight=max(1.0, FTS_TOP_WEIGHT - float(index)),
            )

    for member_id in referenced_member_ids:
        subject_memories = memory_ledger.find_memories_by_entity(
            connection,
            guild_id=guild_id,
            entity_type="subject",
            entity_key=str(member_id),
            reveal_scopes=("cross_member",),
            limit=fetch_limit,
        )
        for memory in subject_memories:
            if memory.guild_id != int(guild_id):
                continue
            if memory.subject_user_id == int(interlocutor_user_id):
                continue
            if not _memory_is_context_revealable(
                memory,
                interlocutor_user_id=interlocutor_user_id,
            ):
                continue
            _add_candidate(
                candidates,
                memory,
                reason=f"referenced_subject:{member_id}",
                weight=REFERENCED_SUBJECT_WEIGHT,
            )

        linked_memories = memory_ledger.find_memories_by_entity(
            connection,
            guild_id=guild_id,
            entity_type="member",
            entity_key=str(member_id),
            reveal_scopes=("cross_member",),
            limit=fetch_limit,
        )
        for memory in linked_memories:
            if memory.guild_id != int(guild_id):
                continue
            if memory.subject_user_id == int(interlocutor_user_id):
                continue
            if not _memory_is_context_revealable(
                memory,
                interlocutor_user_id=interlocutor_user_id,
            ):
                continue
            _add_candidate(
                candidates,
                memory,
                reason=f"referenced_member:{member_id}",
                weight=REFERENCED_MEMBER_WEIGHT,
            )

    return candidates


def _authorized_contradiction_partners(
    connection: sqlite3.Connection,
    *,
    memory: memory_ledger.MemoryRecord,
    interlocutor_user_id: int,
) -> list[memory_ledger.MemoryRecord]:
    partners: list[memory_ledger.MemoryRecord] = []
    for link in memory_ledger.list_contradictions(connection, memory_id=memory.id):
        partner_id = (
            link.right_memory_id if link.left_memory_id == memory.id else link.left_memory_id
        )
        partner = memory_ledger.get_memory(connection, partner_id, required=False)
        if partner is None or not partner.active or partner.guild_id != memory.guild_id:
            continue
        if not _memory_is_context_revealable(
            partner,
            interlocutor_user_id=interlocutor_user_id,
        ):
            continue
        partners.append(partner)
    partners.sort(
        key=lambda item: (item.importance, item.updated_at, item.id),
        reverse=True,
    )
    return partners[:MAX_CONTRADICTION_PARTNERS_PER_MEMORY]


def _expand_contradictions(
    connection: sqlite3.Connection,
    *,
    candidates: dict[int, _Candidate],
    base_selected: Sequence[_Candidate],
    speaker_profile_ids: set[int],
    interlocutor_user_id: int,
) -> set[int]:
    included_ids = {candidate.memory.id for candidate in base_selected}
    for candidate in base_selected:
        for partner in _authorized_contradiction_partners(
            connection,
            memory=candidate.memory,
            interlocutor_user_id=interlocutor_user_id,
        ):
            if partner.id in speaker_profile_ids:
                continue
            weight = max(0.0, candidate.score - float(partner.importance) - 0.01)
            _add_candidate(
                candidates,
                partner,
                reason=f"contradiction:{candidate.memory.id}",
                weight=weight,
            )
            included_ids.add(partner.id)
    return included_ids


def _effective_excerpt(receipt: memory_ledger.MemoryReceipt) -> str:
    value = (
        receipt.edited_excerpt
        if receipt.edited_excerpt is not None
        else receipt.original_excerpt
    )
    cleaned = " ".join(str(value).split())
    return cleaned if cleaned and _content_is_safe(cleaned) else ""


def _clip_excerpt(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return value[: limit - 1].rstrip() + "…"


def _allocate_evidence(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    memory_ids_in_priority_order: Iterable[int],
    char_budget: int,
    receipts_per_memory: int,
) -> dict[int, tuple[ContextEvidence, ...]]:
    remaining = char_budget
    evidence: dict[int, tuple[ContextEvidence, ...]] = {}
    if remaining <= 0 or receipts_per_memory <= 0:
        return evidence

    for memory_id in memory_ids_in_priority_order:
        if remaining <= 0:
            break
        receipts = list(reversed(memory_ledger.list_receipts(connection, memory_id)))
        selected: list[ContextEvidence] = []
        for receipt in receipts:
            if remaining <= 0 or len(selected) >= receipts_per_memory:
                break
            if receipt.guild_id != int(guild_id):
                continue
            excerpt = _effective_excerpt(receipt)
            if not excerpt:
                continue
            clipped = _clip_excerpt(
                excerpt,
                min(MAX_EVIDENCE_EXCERPT_CHARS, remaining),
            )
            if not clipped:
                continue
            selected.append(
                ContextEvidence(
                    receipt_id=receipt.id,
                    memory_id=receipt.memory_id,
                    source_kind=receipt.source_kind,
                    source_context=receipt.source_context,
                    author_user_id=receipt.author_user_id,
                    excerpt=clipped,
                    source_created_at=receipt.source_created_at,
                    source_edited_at=receipt.source_edited_at,
                    source_deleted_at=receipt.source_deleted_at,
                )
            )
            remaining -= len(clipped)
        if selected:
            evidence[memory_id] = tuple(selected)
    return evidence


def _contradiction_ids_for_included_memories(
    connection: sqlite3.Connection,
    *,
    memory: memory_ledger.MemoryRecord,
    included_memory_ids: set[int],
) -> tuple[int, ...]:
    ids: list[int] = []
    for link in memory_ledger.list_contradictions(connection, memory_id=memory.id):
        partner_id = (
            link.right_memory_id if link.left_memory_id == memory.id else link.left_memory_id
        )
        if partner_id in included_memory_ids:
            ids.append(partner_id)
    return tuple(sorted(set(ids)))


def assemble_memory_context(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    interlocutor_user_id: int,
    query: str,
    on_date: date,
    referenced_member_ids: Sequence[int] = (),
    contextual_limit: int = DEFAULT_CONTEXTUAL_LIMIT,
    evidence_char_budget: int = DEFAULT_EVIDENCE_CHAR_BUDGET,
    evidence_per_memory: int = DEFAULT_EVIDENCE_PER_MEMORY,
) -> MemoryContextBundle:
    """Assemble deterministic, authorization-first memory context for future chat.

    The current speaker receives their complete active profile except `admin_only` rows.
    Other members contribute only valid `cross_member` rows. FTS/entity retrieval and
    contradiction expansion happen only after those reveal boundaries are fixed locally.
    This service performs no model call and persists no personality/profile analysis.
    """

    resolved_limit = _bounded_int(
        contextual_limit,
        minimum=1,
        maximum=MAX_CONTEXTUAL_LIMIT,
        field_name="contextual_limit",
    )
    resolved_evidence_budget = _bounded_int(
        evidence_char_budget,
        minimum=0,
        maximum=MAX_EVIDENCE_CHAR_BUDGET,
        field_name="evidence_char_budget",
    )
    resolved_evidence_per_memory = _bounded_int(
        evidence_per_memory,
        minimum=0,
        maximum=MAX_EVIDENCE_PER_MEMORY,
        field_name="evidence_per_memory",
    )
    resolved_references = _normalize_referenced_member_ids(
        referenced_member_ids,
        interlocutor_user_id=interlocutor_user_id,
    )

    stored_identity = member_profiles.get_member_identity(
        connection,
        guild_id=guild_id,
        user_id=interlocutor_user_id,
        required=True,
    )
    assert stored_identity is not None
    identity = stored_identity.trusted_chat_context(on_date=on_date)

    speaker_memories = [
        memory
        for memory in memory_ledger.list_revealable_profile(
            connection,
            guild_id=guild_id,
            subject_user_id=interlocutor_user_id,
            interlocutor_user_id=interlocutor_user_id,
            allow_admin=False,
        )
        if _memory_is_context_revealable(
            memory,
            interlocutor_user_id=interlocutor_user_id,
        )
    ]
    speaker_profile_ids = {memory.id for memory in speaker_memories}

    candidates = _authorized_cross_member_candidates(
        connection,
        guild_id=guild_id,
        interlocutor_user_id=interlocutor_user_id,
        query=query,
        referenced_member_ids=resolved_references,
        contextual_limit=resolved_limit,
    )
    base_selected = sorted(
        candidates.values(),
        key=_candidate_sort_key,
        reverse=True,
    )[:resolved_limit]
    contextual_ids = _expand_contradictions(
        connection,
        candidates=candidates,
        base_selected=base_selected,
        speaker_profile_ids=speaker_profile_ids,
        interlocutor_user_id=interlocutor_user_id,
    )
    contextual_candidates = sorted(
        (
            candidate
            for memory_id, candidate in candidates.items()
            if memory_id in contextual_ids
        ),
        key=_candidate_sort_key,
        reverse=True,
    )

    contextual_priority_ids = [candidate.memory.id for candidate in contextual_candidates]
    speaker_priority_ids = [
        memory.id
        for memory in sorted(
            speaker_memories,
            key=lambda item: (item.importance, item.updated_at, item.id),
            reverse=True,
        )
    ]
    evidence_by_memory = _allocate_evidence(
        connection,
        guild_id=guild_id,
        memory_ids_in_priority_order=(*contextual_priority_ids, *speaker_priority_ids),
        char_budget=resolved_evidence_budget,
        receipts_per_memory=resolved_evidence_per_memory,
    )

    included_ids = speaker_profile_ids | set(contextual_priority_ids)
    speaker_profile = tuple(
        ContextMemory(
            memory=memory,
            relevance_score=float(memory.importance),
            reasons=("speaker_profile",),
            evidence=evidence_by_memory.get(memory.id, ()),
            contradicts_memory_ids=_contradiction_ids_for_included_memories(
                connection,
                memory=memory,
                included_memory_ids=included_ids,
            ),
        )
        for memory in speaker_memories
    )
    contextual_memories = tuple(
        ContextMemory(
            memory=candidate.memory,
            relevance_score=candidate.score,
            reasons=tuple(sorted(candidate.reasons)),
            evidence=evidence_by_memory.get(candidate.memory.id, ()),
            contradicts_memory_ids=_contradiction_ids_for_included_memories(
                connection,
                memory=candidate.memory,
                included_memory_ids=included_ids,
            ),
        )
        for candidate in contextual_candidates
    )

    return MemoryContextBundle(
        guild_id=int(guild_id),
        interlocutor_user_id=int(interlocutor_user_id),
        identity=identity,
        speaker_profile=speaker_profile,
        contextual_memories=contextual_memories,
    )


def _memory_prompt_line(item: ContextMemory) -> str:
    memory = item.memory
    qualifier = "Unverified gossip" if memory.is_gossip else memory.epistemic_label
    contradiction = (
        f" | contradicts={','.join(str(value) for value in item.contradicts_memory_ids)}"
        if item.contradicts_memory_ids
        else ""
    )
    return (
        f"- memory#{memory.id} [{memory.category} | {qualifier} | {memory.reveal_scope}"
        f"{contradiction}] {memory.summary}"
    )


def render_memory_context_for_prompt(bundle: MemoryContextBundle) -> str:
    """Render the locally authorized bundle without changing epistemic labels."""

    lines = [
        "TRUSTED MEMBER IDENTITY",
        f"- discord_display_name: {bundle.identity.discord_display_name}",
        f"- preferred_name: {bundle.identity.preferred_name}",
        f"- birth_date: {bundle.identity.birth_date}",
        f"- age: {bundle.identity.age}",
        "",
        "MEMORY INTERPRETATION RULE",
        "- Fact is factual memory; Inference and Impression are qualified interpretations; "
        "Gossip is unverified.",
        "- Do not treat a qualified interpretation or gossip claim as established fact.",
        "",
        "FULL ACTIVE SPEAKER PROFILE",
    ]
    if bundle.speaker_profile:
        lines.extend(_memory_prompt_line(item) for item in bundle.speaker_profile)
    else:
        lines.append("- No saved speaker memories.")

    lines.extend(("", "RELEVANT CROSS-MEMBER CONTEXT"))
    if bundle.contextual_memories:
        lines.extend(_memory_prompt_line(item) for item in bundle.contextual_memories)
    else:
        lines.append("- No additional cross-member context selected.")

    evidence_items = [*bundle.contextual_memories, *bundle.speaker_profile]
    lines.extend(("", "EVIDENCE RECEIPTS"))
    emitted = False
    for item in evidence_items:
        for receipt in item.evidence:
            emitted = True
            deleted = " | source_deleted_after_capture" if receipt.source_deleted_at else ""
            lines.append(
                f"- memory#{item.memory.id} receipt#{receipt.receipt_id} "
                f"[{receipt.source_context} | author={receipt.author_user_id}{deleted}] "
                f"{receipt.excerpt}"
            )
    if not emitted:
        lines.append("- No receipt excerpts included in this context budget.")
    return "\n".join(lines)
