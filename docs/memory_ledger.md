# Memory Ledger

The Memory Ledger is Wilhelmina's private, persistent local memory. SQLite is the canonical source of truth. OpenAI may interpret already-authorized text or reason over already-authorized context, but model output never authorizes access, disclosure, replacement, or deletion.

The product target remains an adult social character: sharp, vulgar, funny, intrusive when useful, and able to remember callbacks, contradictions, preferences, gossip, names, birthdays, projects, and other ordinary social context. Target voice: **mean enough to delight the room, sharp enough to feel intelligent, and still useful.**

Quality and memory richness take priority over minimizing model/token cost. Privacy controls exist to prevent dangerous retention or disclosure, not to make Wilhelmina artificially stupid.

## Current persistence status

### Member identity schema v8

The private identity profile stores:

- current Discord display name through the Registry;
- member-provided preferred name;
- full self-reported birth date;
- adult-memory consent timestamp;
- version of the memory disclosure accepted.

The current disclosure covers interaction memory, DMs directly with Wilhelmina, and ordinary cross-member social callbacks. Legacy consent is not silently upgraded. Full birth date remains canonical and current age is calculated locally when trusted context is assembled.

### Memory Ledger schema v9

Phase 2 upgrades the Memory Ledger from v6 to v9. Version 8 is already occupied by identity-consent migration, so v9 is the next persistence version.

Schema v9 contains:

- `memory_ledger_settings`;
- `memory_records`;
- `memory_receipts`;
- `memory_contradictions`;
- `memory_entities`;
- `memory_search` (SQLite FTS5 virtual table and sync triggers).

Automatic Discord extraction and the live chat surface are **not** implemented by this schema phase. They remain later phases.

## Memory record

Every memory remains guild-scoped and attached to an existing Coven Registry/profile shell. No outsider profile is created merely because somebody gossips about a third party.

A v9 memory stores:

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

Categories remain:

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

Epistemic labels remain:

- `Fact`
- `Inference`
- `Impression`
- `Gossip`

Gossip is always treated as attributed/unverified social information rather than established fact.

## Privacy and reveal metadata

Schema v9 separates **what a memory is** from **where it may be revealed**.

### Privacy class

- `ordinary` — normal adult social memory eligible for approved conversational use.
- `restricted` — material that requires a narrower reveal scope.

### Reveal scope

- `cross_member` — may be used in approved memory-aware conversation even when the current interlocutor is somebody else. This is the default for ordinary social memories and implements the locked "full menace" direction.
- `owner_only` — may be revealed only when the current interlocutor is the memory's subject.
- `admin_only` — never enters ordinary member chat; reserved for founder/admin surfaces.

`restricted + cross_member` is invalid. An `Admin note` is always forced to `restricted/admin_only` regardless of caller input.

These fields are deterministic local authorization metadata. OpenAI never gets to override them.

### Importance

`importance` is an integer from 0 through 100, default 50. It is a local retrieval/ranking signal for later context assembly. It is not an authorization signal and does not override reveal scope.

## Receipts and source context

Every memory has evidence.

Schema v9 adds `source_context` so a receipt can honestly represent where the evidence came from:

- `guild` — Discord guild message. Requires channel ID, message ID, and jump URL.
- `dm` — direct message involving Wilhelmina. Requires message ID but **does not fabricate a guild jump URL**. A DM channel ID may be retained if the event layer has one, but it is not treated as a guild channel.
- `admin` — founder/admin-authored memory. No Discord channel, message, or jump URL is fabricated.

Discord receipts retain:

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

Deleting the original Discord message does not erase an already-captured receipt. It marks the source deleted. Permanently deleting the Memory Ledger record itself cascades its receipts.

## Duplicate, replacement, and contradiction behavior

All destructive decisions remain Python/SQLite behavior.

### Exact duplicate

An exact duplicate keeps one memory record, adds the new receipt, and updates confirmation timestamps.

### Topic-scoped correction

Ordinary replacement is **topic-scoped**, not category-wide.

A new ordinary memory replaces older active ordinary memories only when all of the following match:

- same guild;
- same subject;
- same normalized `topic_key`.

Unrelated memories in the same category coexist. For example, changing a coffee preference does not erase a movie preference merely because both are `Preference` memories.

Superseded ordinary records and their receipts are permanently deleted. A minimal content-free `memory.replaced` audit remains.

The legacy service parameter named `replace_normal_category` is temporarily preserved for compatibility; in v9 it controls topic-scoped replacement and no longer authorizes category-wide deletion.

### Gossip contradiction

Multiple gossip claims about the same topic remain separate and are linked through `memory_contradictions`.

If a gossip record's topic/category changes, old contradiction links are cleared before valid links are regenerated. Deleting either memory cascades the relationship.

## Entity index

`memory_entities` provides deterministic local relationship/index data for later retrieval. Supported entity types are:

- `subject` — automatically managed member who owns the memory;
- `topic` — automatically managed normalized topic key;
- `member` — additional participating/referenced Coven member IDs or member keys;
- `term` — bounded normalized terms useful for deterministic lookup.

`subject` and `topic` links are system-managed and cannot be overwritten through the public entity API. Custom entity replacement may change `member` and `term` links only.

Deleting a memory cascades all entity links.

## Local full-text search

`memory_search` is an SQLite FTS5 external-content index over:

- memory summary;
- topic key.

Insert/update/delete triggers keep it synchronized with `memory_records`.

The service exposes local search with deterministic filters for:

- guild;
- reveal scope;
- optional subject IDs;
- bounded result limit.

Search defaults to `cross_member` records only. A later owner-context assembler may explicitly include `owner_only`. Admin-only records are never accidentally returned by the normal default.

Entity lookup uses the same reveal-scope principle.

This search layer is for local retrieval. OpenAI is **not** asked which private rows it is allowed to retrieve.

## Full-profile contract

The current interlocutor's full permitted active profile remains core future chat context. FTS/entity retrieval is not a penny-saving excuse to amputate that profile.

Later retrieval uses these structures primarily for:

- relevant cross-member memories;
- named/referenced members;
- contradiction partners;
- useful historical callbacks;
- evidence/receipt budgeting.

Authorization is applied before context is sent to the model.

## Audit privacy

Operational audit rows must not serialize memory summaries or receipt excerpts.

Schema-v9 service events keep only content-free metadata such as:

- memory ID;
- whether a record was created or merged;
- whether fields changed;
- privacy/reveal class;
- receipt source context.

Permanent deletion/replacement audits remain content-free.

Raw memories and receipts belong in the Memory Ledger, not generic audit logs.

## Prohibited information

The deterministic local validator runs before external extraction and before persistence. At minimum it rejects material matching dangerous classes such as:

- passwords and login credentials;
- API/access tokens;
- banking/payment/account information;
- government/private identity-document numbers;
- exact home/private addresses;
- medical or mental-health diagnoses;
- comparable dangerous private secrets.

A DM sent directly to Wilhelmina is not rejected merely because it is private. Third-party DMs Wilhelmina is not part of remain outside accessible collection scope.

Adult/social character direction never converts prohibited secrets or admin-only data into comedy ammunition.

## Collection policy

Automatic collection is still controlled separately by the Phase-1 runtime policy:

- `off` — no automatic extraction;
- `interaction` — eligible interaction involving Wilhelmina;
- `ambient` — dormant future whole-server path requiring every platform/runtime gate.

The default remains `off`.

Phase 2 supplies durable local structures only; it does not activate automatic collection.

## v6 → v9 migration matrix

Migration is idempotent and preserves existing content.

| Existing v6 data | v9 result |
|---|---|
| ordinary memory | preserved; `privacy_class=ordinary`, `reveal_scope=cross_member`, `importance=50` |
| `Admin note` | preserved but tightened to `restricted/admin_only` |
| guild Discord receipt | preserved and marked `source_context=guild` |
| admin receipt | preserved and marked `source_context=admin` |
| memory subject/topic | backfilled into system entity rows |
| existing summary/topic | rebuilt into local FTS index |
| receipts/contradictions | preserved subject to existing foreign-key integrity |

The migration order is deliberate:

1. ensure base Registry/profile dependencies;
2. ensure core memory tables exist;
3. add new record columns to legacy tables;
4. rebuild the receipt table into the v9 context-aware shape when required;
5. create indexes that reference new columns;
6. create/rebuild FTS and triggers;
7. backfill subject/topic entity rows;
8. record schema version 9.

Indexes never reference v9 columns before those columns exist.

## Integrity checks

`check_memory_integrity()` provides a local Phase-2 diagnostic for:

- SQLite foreign-key violations;
- orphan/mismatched entity rows;
- invalid contradiction relationships;
- missing system subject/topic entities;
- presence of the FTS structure.

Tests also verify that deleting a memory removes dependent receipts, entity rows, contradiction links, and FTS searchability.

## Rollback notes

Do not downgrade an already-migrated production database by merely running older code against it.

Safe rollback for this phase is operational:

1. stop Wilhelmina before changing database code;
2. restore the pre-v9 SQLite backup/snapshot together with the previous application revision; or
3. if no database rollback is needed, deploy a forward fix that continues understanding v9.

The migration intentionally does not keep duplicated private-content backup tables after success. Old receipt rows are copied into the v9 table and the temporary legacy table is dropped in the same transaction managed by the caller.

## Remaining implementation phases

### Phase 3 — Memory controls

Founder/admin commands, required member data controls, persistent pause/resume/channel controls, authorization and privacy tests.

### Phase 4 — Automatic memory extraction

Discord interaction/DM event eligibility, local prohibited-data guard, strict structured OpenAI extraction, queue/backpressure, receipt/edit/delete reconciliation.

### Phase 5 — Memory intelligence/context

Deterministic scoring, FTS/entity retrieval, full active speaker profile loading, cross-member selection, contradiction expansion, evidence budgeting.

### Phase 6 — Wilhelmina chat brain

Designated server chat, fully memory-aware DM confessional mode, direct responses, selective spontaneous interjections, adult persona/evals.

### Phase 7 — Hardening and dormant ambient path

Adversarial/privacy regressions, reconnect/rate-limit testing, observability/rollback controls, and the ambient whole-server path kept disabled until every required gate is satisfied.
