# Phase 5 — Memory context intelligence

## Purpose

Phase 5 turns the existing Memory Ledger into deterministic conversational context for the later Phase-6 chat brain.

It does **not** create a new Discord command, does not listen to new sources, does not call OpenAI, and does not persist a new personality/relationship dossier. It decides which already-stored, already-authorized memory rows are appropriate to place into a future chat prompt.

The core rule is:

> **Authorization happens before relevance ranking. A memory cannot become revealable merely because it is relevant, recent, important, or contradictory.**

SQLite remains canonical. The context assembler is local Python code.

## Context bundle

`services.memory_context.assemble_memory_context(...)` produces four things:

1. trusted identity context for the current interlocutor;
2. the current interlocutor's complete permitted active Memory Ledger profile;
3. a bounded set of relevant cross-member memories selected from FTS/member-entity retrieval;
4. bounded evidence receipts for the included memories.

The renderer preserves the existing epistemic distinction:

- `Fact` — factual memory;
- `Inference` — qualified interpretation, not established fact;
- `Impression` — qualified Wilhelmina/member impression, not established fact;
- `Gossip` — attributed/unverified social claim.

Phase 5 does not collapse these labels into one truth bucket.

## Authorization matrix

| Memory owner | `cross_member` | `owner_only` | `admin_only` |
|---|---:|---:|---:|
| Current speaker | included in full profile | included in full profile | never included |
| Another member | eligible for contextual retrieval | never included | never included |

The current speaker therefore receives their full *permitted* active profile rather than a token-saving subset. Cross-member retrieval remains selective so Wilhelmina does not indiscriminately dump every other member's memory into every conversation.

`restricted + cross_member` remains invalid at the Memory Ledger layer. Phase 5 also treats that combination as non-revealable if a malformed legacy/manually-edited row somehow exists despite normal service validation. `Admin note` remains forced to `restricted/admin_only` and cannot enter ordinary chat context.

## Retrieval-time dangerous-secret guard

Phase 5 revalidates memory summaries and receipt excerpts against the existing deterministic dangerous-secret guard before placing them in conversational context.

This is deliberate defense in depth for old or manually modified databases. A legacy row containing a password, authentication token, payment credential, exact private identity-document number, doxxing-grade address, or comparable hard secret is not allowed to become prompt context merely because it predates the current ingestion guards.

A memory whose summary fails the guard is excluded from context. If the summary is safe but an old receipt excerpt fails the guard, the memory may still be included while that unsafe receipt excerpt is omitted.

This does **not** reintroduce subject-matter censorship. Medical, mental-health, adult relationship/sexual, political, religious, identity-related, substance-use, embarrassing, gossip, and other socially sensitive material remains permitted when it does not match an actual hard-secret boundary.

## Retrieval inputs

The assembler accepts:

- the current guild ID;
- the current interlocutor/member ID;
- the current conversational query text;
- the server date used to calculate age from the canonical full birthday;
- optional member IDs that trusted Discord-facing code has already resolved as explicitly referenced members.

The member-reference input is not a model authorization channel. Phase 6 may later pass Discord-resolved mentions/references into this interface; a model must not be allowed to invent an arbitrary member ID and thereby widen access.

## Full speaker profile

The full active speaker profile is loaded first with deterministic reveal checks.

This includes permitted social memory regardless of whether its subject matter is medical, mental-health related, romantic, sexual between adults, political, religious, identity-related, embarrassing, substance-related, or otherwise socially sensitive.

It does not include `admin_only` rows, invalid `restricted/cross_member` rows, or a legacy memory whose summary trips the hard-secret guard.

Because the full profile is a first-class product requirement, FTS is not used as an excuse to omit the speaker's other permitted memories.

## Cross-member FTS retrieval

FTS searches `memory_search` only through `cross_member` reveal scope for other members.

Rows with `owner_only` or `admin_only` scope never enter the candidate set. This means a hidden importance-100 row cannot beat an allowed importance-1 row: the hidden row is removed before scoring exists.

Speaker-owned FTS hits are not duplicated into the contextual section because the complete permitted speaker profile is already present.

Emoji-only or otherwise non-searchable conversational text does not fail the context request; the assembler simply skips FTS and still returns the speaker profile.

`search_memories(...)` already returns SQLite FTS5/BM25 results in best-first order. Phase 5 converts that returned ordering into a descending deterministic FTS priority rather than attempting to reinterpret the raw BM25 number, which can be negative and extremely small.

## Member/entity retrieval

For explicitly referenced members, Phase 5 checks two existing local entity indexes using `cross_member` scope only:

- `subject:<member id>` — memories whose subject is the referenced member;
- `member:<member id>` — memories about another subject that explicitly link the referenced member.

This allows relevant relationship/social context to appear without making name/entity resolution a model-controlled authorization decision.

## Deterministic ranking

Only authorized cross-member candidates are ranked.

The current implementation gives deterministic priority to:

1. memories whose subject is an explicitly referenced member;
2. memories carrying an explicit `member` entity link to a referenced member;
3. best-first FTS matches in the order returned by the Ledger search service;
4. the memory's existing `importance` signal and deterministic recency/ID tie-breaks.

These weights are retrieval mechanics, not privacy mechanics. No score can widen reveal scope.

## Contradiction expansion

After the base contextual set is chosen, linked contradiction partners may be added.

Every contradiction partner is independently checked again through the same Phase-5 reveal/secret boundary for the current interlocutor.

Therefore:

- revealable contradictory gossip may travel together so Wilhelmina can see the conflict;
- another member's `owner_only` contradiction partner remains hidden;
- `admin_only` contradiction partners remain hidden;
- invalid `restricted/cross_member` partners remain hidden;
- legacy hard-secret partners remain hidden;
- wrong-guild partners are rejected;
- the prompt records which included memory IDs contradict each other.

Contradiction expansion is bounded per selected memory so a pathological graph cannot grow prompt context without limit.

## Evidence budget

Memory summaries remain available even when receipt evidence reaches its budget.

Evidence is added separately with generous deterministic bounds:

- default total receipt-excerpt budget: 16,000 characters;
- default maximum receipts per memory: 2;
- default maximum excerpt contribution per receipt: 1,200 characters.

Contextually selected memories receive evidence priority, followed by high-importance speaker-profile memories.

For an edited source receipt, the latest authorized `edited_excerpt` is used instead of the original wording. If Discord later deleted the source message, the previously retained receipt remains available as evidence and is marked as deleted-after-capture; Phase 5 does not fabricate current source availability.

Unsafe legacy receipt excerpts are omitted before budgeting. The evidence budget exists to prevent unbounded raw-history growth, not to optimize away useful intelligence for token cost.

## Identity context

A completed private member identity profile is required before assembly.

The trusted identity section contains the already-approved local context:

- current Discord display name;
- preferred name;
- full canonical birth date;
- age calculated locally for the supplied server date.

There is no adult-memory-consent/version permission gate.

The existing under-18 profile-completion behavior remains **PRODUCT DECISION PENDING** and is not changed or expanded in Phase 5.

## Personality-analysis boundary

Phase 5 contextual retrieval is intentionally separate from the proposed permanent/evolving personality-analysis layer.

This PR may retrieve existing `Inference` and `Impression` records while preserving their qualified epistemic labels, but it does **not**:

- create psychological scores;
- infer personality traits from conversation as a new persistent feature;
- build relationship dossiers;
- persist a new analyzed personality profile;
- run a model pass that converts Discord activity into permanent behavioral profiling.

The broader permanent/evolving personality-analysis feature remains behind the repository's separately recorded external-policy/release gate. Phase 5 does not silently narrow that long-term product vision, and it does not silently ignore the gate.

## What a future Discord member experiences

Nothing new is user-facing yet. Phase 5 is infrastructure for Phase 6.

When Phase 6 is built, this layer is what allows Wilhelmina to:

- remember the current speaker's established preferences/history without forgetting unrelated profile context;
- pull in relevant cross-member callbacks when the current topic or referenced person makes them useful;
- know when two gossip claims conflict;
- preserve whether something was fact, inference, impression, or gossip;
- avoid exposing another person's owner-only memory or any admin-only record;
- avoid resurfacing a legacy hard secret that should never enter conversation context.

## What the founder/admin experiences

No new admin command is added. Existing `/memory-admin` controls remain the authoritative inspection/correction/deletion surface.

Explicit privacy/reveal edits continue to take effect immediately because context assembly reads the current Memory Ledger state every time.

## Rollback

Phase 5 adds no database migration and no new persisted context table.

Rolling it back means deploying the previous application revision or simply not wiring the service into the future Phase-6 chat cog. Existing identity, Memory Ledger, extraction queue, receipts, entities, contradictions, FTS, and admin controls remain intact.

## Validation contract

Automated tests must cover at minimum:

- complete permitted speaker profile loading;
- `admin_only` exclusion;
- other-member `owner_only` exclusion;
- malformed `restricted/cross_member` fail-closed behavior;
- retrieval-time legacy hard-secret exclusion;
- authorization before importance/relevance ranking;
- referenced subject/member entity retrieval;
- FTS best-first ordering preservation;
- deterministic ranking behavior;
- revealable contradiction expansion;
- hidden contradiction filtering;
- wrong-guild isolation;
- bounded evidence and latest edited evidence;
- unsafe legacy receipt omission;
- epistemic/gossip label preservation;
- missing identity profile fail-closed behavior;
- non-searchable query fallback.

Repository quality gates remain:

```bash
ruff check .
pytest
```
