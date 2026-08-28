# Memory Ledger

The Memory Ledger is Wilhelmina's private, persistent local memory. SQLite is the canonical source of truth. OpenAI may interpret already-authorized text or reason over already-authorized context, but model output never authorizes access, disclosure, replacement, or deletion.

The product target is a sharp, socially aware character that remembers callbacks, contradictions, preferences, gossip, names, birthdays, projects, relationships, communication habits, and other useful social context. Privacy controls exist to prevent dangerous retention or disclosure, not to flatten ordinary social memory.

## Current persistence layers

### Private member identity — schema v12

The identity profile stores:

- guild ID;
- Discord user ID;
- member-provided preferred name;
- full self-reported birth date;
- created/updated timestamps.

Current Discord display name remains in the Coven Registry and is joined into trusted identity context. Full birth date is canonical; age is calculated locally for the relevant date.

Schema v12 physically removes the former `adult_memory_consent_at` and `memory_consent_version` fields. Memory/chat authorization does not depend on a consent phrase or disclosure-version token. A completed private profile is only the identity prerequisite; runtime/source/privacy gates remain separate.

The existing under-18 profile-completion behavior remains unchanged and is **PRODUCT DECISION PENDING**.

### Memory Ledger — schema v9

The persistent ledger contains:

- `memory_ledger_settings`;
- `memory_records`;
- `memory_receipts`;
- `memory_contradictions`;
- `memory_entities`;
- `memory_search` (SQLite FTS5 plus sync triggers).

### Automatic extraction queue — schema v11

`memory_extraction_jobs` is the durable transient-work queue for interaction-scoped automatic extraction. Its v11 ownership model includes claim tokens, leases, bounded retry, source versions, absolute raw-text TTL enforcement, and migration protection against legacy tokenless workers.

Phase 5 adds no new persistent table. `services.memory_context` reads the current identity/Ledger state and returns an in-memory authorization-filtered context bundle for the later chat brain.

## Memory record

Every memory is guild-scoped and attached to an existing Coven member/profile shell. Gossip about a non-member does not silently create an outsider profile.

A memory stores:

- guild ID;
- subject/member ID;
- category;
- epistemic label;
- concise summary;
- normalized duplicate key;
- normalized topic key;
- gossip flag;
- active flag;
- privacy class;
- reveal scope;
- retrieval importance;
- creator ID;
- created, updated, and last-confirmed timestamps.

Categories:

- `Identity`
- `Preference`
- `Dislike`
- `Boundary`
- `Interest`
- `Project`
- `Relationship context`
- `Communication style`
- `Important event`
- `Admin note`
- `Wilhelmina impression`
- `Gossip`

Epistemic labels:

- `Fact`
- `Inference`
- `Impression`
- `Gossip`

Facts, inferences, impressions, and gossip remain distinguishable. Gossip is attributed/unverified social information rather than established fact.

## Privacy and reveal metadata

### Privacy class

- `ordinary` — normal social memory eligible for approved conversational use.
- `restricted` — material requiring a narrower reveal scope.

### Reveal scope

- `cross_member` — may be used in approved memory-aware conversation when the current interlocutor is another permitted member.
- `owner_only` — may be revealed only when the current interlocutor is the memory's subject.
- `admin_only` — reserved for founder/admin surfaces and excluded from ordinary member chat.

`restricted + cross_member` is invalid. `Admin note` is always forced to `restricted/admin_only`.

These fields are deterministic local authorization metadata. OpenAI never overrides them.

Phase 5 additionally fails closed if a malformed legacy/manually-edited `restricted/cross_member` row exists despite normal service validation.

### Importance

`importance` is an integer from 0 through 100, default 50. It is a retrieval/ranking signal, not authorization, and never overrides reveal scope.

## Receipts and evidence

Every surviving memory has evidence.

Receipt `source_context` values:

- `guild` — Discord guild message, with channel/message IDs and jump URL;
- `dm` — DM involving Wilhelmina, with message ID and no fabricated guild jump URL;
- `admin` — founder/admin-authored memory, with no fabricated Discord message metadata.

Discord receipts may retain:

- source author;
- source context;
- channel ID when applicable;
- message ID;
- jump URL when applicable;
- original excerpt;
- latest edited excerpt;
- source creation timestamp;
- edit timestamp;
- source deletion timestamp.

Deleting the source Discord message marks an existing receipt deleted; it does not rewrite history. Permanently deleting the Memory Ledger record cascades its receipts.

## Duplicate, replacement, and contradiction behavior

All destructive or authorization-sensitive decisions remain Python/SQLite behavior.

### Exact duplicate

An exact duplicate keeps one memory record, adds a new receipt, and updates confirmation timestamps.

**Duplicate confirmation is evidence-only.** It does not implicitly change privacy class, reveal scope, or importance. This applies even when a later admin `/memory-admin add` invocation supplies different metadata.

Privacy/reveal/importance changes require an explicit admin edit. `/memory-admin edit` may intentionally tighten or loosen privacy/reveal metadata as long as the requested pair is valid. This keeps “confirm the same fact again” separate from “change how this memory may be disclosed.”

### Topic-scoped correction

Ordinary replacement is topic-scoped, not category-wide. A new ordinary memory replaces older active ordinary memories only when guild, subject, and normalized `topic_key` match.

Unrelated memories in the same category coexist. Superseded ordinary records and their receipts are permanently deleted, with only content-free audit metadata retained.

### Gossip contradiction

Conflicting gossip on the same topic may coexist and is linked through `memory_contradictions`. Editing a gossip record's topic/category clears obsolete links before valid links are regenerated. Deleting either memory cascades the relationship.

Phase 5 may expand a selected gossip memory with bounded contradiction partners, but every partner is independently rechecked for the current interlocutor before it can enter context.

## Entity index

`memory_entities` provides deterministic local relationship/index data for retrieval.

Supported types:

- `subject` — system-managed owner of the memory;
- `topic` — system-managed normalized topic;
- `member` — other participating/referenced Coven member identifiers;
- `term` — bounded normalized terms useful for deterministic lookup.

`subject` and `topic` are system-managed. Custom entity replacement may modify only `member` and `term` links. Memory deletion cascades entity rows.

## Local full-text search

`memory_search` is an SQLite FTS5 external-content index over summary and topic key. Insert/update/delete triggers keep it synchronized.

Search supports deterministic filters for guild, reveal scope, optional subject IDs, and bounded result count. Normal search defaults to `cross_member`; owner/admin contexts must request their additional scopes explicitly.

OpenAI is never asked which private rows it is allowed to retrieve.

Phase 5 consumes the existing best-first FTS ordering rather than reinterpreting raw BM25 sign/magnitude, then combines that deterministic priority with explicit member-reference and importance signals after authorization.

## Full-profile and Phase 5 retrieval contract

The current interlocutor's full permitted active profile is core chat context. Phase 5 loads that profile first: the speaker's own `cross_member` and `owner_only` rows are eligible, while `admin_only`, invalid `restricted/cross_member`, and legacy hard-secret rows are excluded.

FTS/entity retrieval supplements the speaker profile with relevant **other-member `cross_member`** memories, named/referenced members, contradiction partners, historical callbacks, and bounded evidence receipts.

Authorization is applied before relevance ranking. A high-importance or highly relevant hidden row therefore cannot outrank its way into context.

Explicit member-reference IDs are a trusted service input intended for later Discord-resolved mentions/references. They are not a model-controlled authorization mechanism.

A distinct permanent/evolving psychological/personality-profiling layer remains externally policy-gated and is not smuggled into ordinary retrieval architecture. Phase 5 may retrieve existing `Inference` and `Impression` memories while preserving those qualified epistemic labels; it does not create a new analyzed personality dossier.

See `docs/memory_context.md` for the complete Phase-5 contract.

## Dangerous-secret boundary

Sensitivity by topic is not itself prohibited. Medical or mental-health diagnoses, adult relationship/sexual context, politics, religion, identity, substance use, money, embarrassment, and other ordinary social material may be valid memory when the actual source/authorization rules permit it.

The deterministic local guard instead rejects concrete dangerous-secret classes, including recognizable forms of:

- passwords/login credentials;
- API keys/access tokens/private secrets;
- payment-card/banking/account credentials;
- government/private identity-document numbers;
- doxxing-grade exact private addresses;
- equivalent high-risk secrets.

The guard runs before provider use and again on model-controlled persisted strings such as summary/topic/term entities. Phase 5 also revalidates summaries and receipt excerpts at retrieval time so an unsafe legacy or manually modified row cannot bypass the modern ingestion guards and reappear in a future chat prompt.

If a legacy memory summary fails the guard, that memory is excluded from context. If a summary is safe but a legacy receipt excerpt fails, the memory may remain while that unsafe evidence excerpt is omitted.

Admin-only information and unauthorized sources remain outside ordinary disclosure regardless of content category.

A DM sent directly to Wilhelmina is not rejected merely for being private. Third-party DMs Wilhelmina is not part of remain inaccessible.

## Automatic interaction-scoped extraction

Automatic collection is controlled by:

- `ENABLE_MEMORY_EXTRACTION` feature loading;
- `MEMORY_COLLECTION_MODE` runtime policy;
- persistent pause/resume state;
- completed private identity profile;
- home-guild/source interaction checks;
- private provider readiness;
- deterministic dangerous-secret guard.

Current eligible interaction sources are DMs with Wilhelmina, the designated Wilhelmina channel, direct mentions, and resolvable replies to Wilhelmina. Ambient unaddressed whole-server listening remains dormant.

The queue/worker rechecks authorization before queue persistence, before provider use, and inside the final mutation transaction. A provider response is accepted only when the current row still matches status, content hash, and exact claim token after a final stale-job/TTL sweep.

## Edit and deletion ordering

Raw Discord edits are versioned with full timestamp precision. The edit transaction rejects stale/equal handlers, cancels superseded queue work, advances source version state, rechecks authorization, guards the new text, updates authorized receipt evidence, and requeues only the newest valid version.

A stale worker or late edit handler cannot resurrect superseded text.

Discord source deletion clears outstanding queued source text and marks existing receipts deleted.

## Transient raw-text TTL

Raw source text in outstanding extraction jobs has an absolute one-hour lifetime. Retry and provider processing do not extend it. An independent retention worker can revoke an in-flight claim, and the provider-return transaction runs another expiry sweep before reconciliation.

A provider result returning after TTL therefore creates neither memory nor receipt mutation.

## Audit privacy

Operational audit rows must not serialize memory summaries, receipt excerpts, preferred names, or birth dates.

Safe audit metadata includes identifiers/counts, whether a record was created/merged/replaced, privacy/reveal class changes, and source context. Raw memories and receipts belong in the Memory Ledger, not generic logs.

## Founder/admin controls

`cogs.memory_admin` is enabled by `ENABLE_MEMORY_ADMIN=true` and is ephemeral, administrator-only, and home-guild restricted.

Implemented controls include:

- status/integrity diagnostics;
- persistent pause/resume;
- designated channel set/clear;
- private profile/detail/receipt inspection;
- local FTS search across explicit admin-visible scopes;
- manual add/edit/delete;
- current/departed member data inventory;
- current/departed member-wide Memory Ledger deletion with explicit confirmation.

Single-record deletion requires `DELETE`. Member-wide deletion requires `DELETE MEMBER`.

Member-wide deletion removes subject memories plus receipts the member authored on other subjects. If deleting authored evidence leaves another memory with zero receipts, that evidence-less memory is deleted; otherwise it survives.

The purge does not silently delete Coven Registry or private identity records.

See `docs/memory_controls.md` for command details.

## Migration and rollback

### Memory Ledger v6 -> v9

The v9 migration preserves legacy memories/receipts, adds privacy/reveal/importance/source-context fields, backfills system entities, rebuilds FTS, and keeps foreign-key integrity. `Admin note` data is tightened to `restricted/admin_only` during the schema migration because that is a deterministic invariant of the record type.

### Extraction v10 -> v11

Legacy tokenless `processing` rows are invalidated, transient text is erased, claims are cleared, and database enforcement blocks old-style processing transitions without a claim token. Old v10 workers should still be stopped/drained during rollout.

### Identity v7/v8 -> v12

The private identity table is transactionally rebuilt without the obsolete consent columns while preserving preferred name, full birth date, guild/user identity, and original timestamps. A failed copy rolls back to the intact legacy table.

### Phase 5 context layer

Phase 5 has no database migration and persists no context cache/profile table. Rollback is application-only: do not wire/use the context service from the later chat brain, or deploy the previous application revision. Existing Ledger/identity/extraction data is unchanged.

Do not “rollback” a migrated production database by merely deploying older code. Stop Wilhelmina and restore a matching database backup with the matching application revision, or deploy a forward fix that understands the current schemas.

## Integrity and tests

`check_memory_integrity()` covers foreign-key violations, entity consistency, contradiction validity, required system entities, and FTS presence.

The regression suite additionally covers:

- v7/v8 identity -> v12 preservation and rollback safety;
- v10 extraction -> v11 claim migration;
- secret/identifier/payment/address blocking;
- socially sensitive content permissiveness;
- exact claim ownership and stale-worker rejection;
- absolute TTL including provider-return boundary;
- uncached/raw edit handling and subsecond ordering;
- source deletion;
- explicit-only privacy metadata mutation;
- member-wide authored-evidence deletion;
- content-free operational logging/auditing;
- complete permitted speaker-profile loading;
- owner/admin reveal-scope isolation;
- malformed `restricted/cross_member` fail-closed behavior;
- authorization-before-ranking;
- referenced-member/entity retrieval;
- FTS ordering preservation;
- contradiction expansion/filtering;
- wrong-guild context isolation;
- bounded evidence with latest-edit preference;
- retrieval-time legacy hard-secret exclusion;
- epistemic/gossip preservation.

Repository quality gates:

```bash
ruff check .
pytest
```

## Current and next implementation stages

### Phase 5 — Memory intelligence/context — current work

Authorization-first scoring, full active-speaker profile loading, FTS/entity cross-member selection, contradiction expansion, evidence budgeting, retrieval-time hard-secret defense, and prompt-ready epistemic rendering are implemented in the current stacked Phase-5 branch and remain subject to exact-head CI/review before any merge.

### Phase 6 — Wilhelmina chat brain

Designated server chat and memory-aware direct interaction surfaces using the approved retrieval context.

### Phase 7 — Hardening / deployment / dormant ambient path

Deployment, backups, monitoring, live validation, reconnect/rate-limit/adversarial testing, and any broader listening path only after its separate product/platform decision.
