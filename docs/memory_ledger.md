# Memory Ledger

The Memory Ledger is Wilhelmina's private, persistent local memory for eligible human interactions. SQLite is the canonical source of truth. OpenAI may interpret or phrase approved context for a request, but OpenAI does not own the memory database and model output never directly authorizes access, deletion, replacement, or disclosure.

This document is the implementation contract for the next memory-aware phases. PR #33 already implements the schema-v6 persistence foundation. Automatic extraction, local retrieval intelligence, and live Wilhelmina chat are later phases and must not be treated as already deployed.

## Product direction

Wilhelmina is an adult social character, not a sanitized support bot. The intended experience is profane, sharp, funny, intrusive when useful, and capable of remembering callbacks, contradictions, preferences, embarrassing details, gossip, names, birthdays, projects, and other ordinary social context.

Target voice: **mean enough to delight the room, sharp enough to feel intelligent, and still useful.**

Quality and memory richness take priority over minimizing model or token cost. Privacy controls should minimize unnecessary retention and accidental disclosure without deliberately making Wilhelmina dumber.

## Collection modes

Automatic collection is controlled by an explicit fail-closed runtime mode:

- `off` — no automatic memory extraction;
- `interaction` — eligible interactions involving Wilhelmina may be extracted;
- `ambient` — future broad guild listening, subject to additional hard gates.

The default is `off`.

### Interaction collection

The approved near-term target is `interaction` mode. Eligible sources may include:

- a direct message sent to Wilhelmina;
- a guild message that directly mentions Wilhelmina;
- a reply to Wilhelmina;
- an active direct conversation with Wilhelmina;
- a later explicit remember action.

A DM is eligible only when Wilhelmina is herself a participant. Wilhelmina cannot read or collect DMs between other people.

Only human-authored text is eligible. Bot messages, webhook messages, automated integrations, images, audio, video, uploaded files, and external-link contents are excluded.

There is no history import or backfill.

### Future ambient collection

The product vision keeps a future "ears everywhere" path so Wilhelmina may eventually learn from broader server conversation when platform rules and deployment approval make that appropriate.

Ambient collection must remain fail-closed. It is considered ready only when all of the following are present:

1. `MEMORY_COLLECTION_MODE=ambient`;
2. `ENABLE_AMBIENT_MEMORY=true`;
3. a non-empty `AMBIENT_MEMORY_APPROVAL_REFERENCE` documenting the required platform clarification/approval.

One switch alone must never activate broad listening. The extraction/event phase must reject ambient messages before any OpenAI request when the full gate is not satisfied.

## Consent and adult identity

The memory experience is adult-only. Induction records a full self-reported birth date and rejects members under eighteen.

The adult-memory disclosure is versioned. The current disclosure covers the intended richer behavior: messages sent to Wilhelmina, including DMs, may be remembered, and ordinary social memories may later resurface in approved conversations, including conversations with other participating adult members.

Legacy consent is not silently upgraded. An older profile may remain stored, but trusted memory-aware context is blocked until the current disclosure is accepted.

The private identity profile preserves two distinct names:

- the member's current Discord display name;
- the preferred name explicitly given to Wilhelmina.

The full birth date remains the canonical source of truth. Python calculates current age locally. In an already-authorized trusted memory-aware request, Wilhelmina may receive both names, the full birth date, and calculated age so she can use birthday/age context naturally. These values do not belong in public Registry cards, generic logs, or unrelated AI features.

## Visibility and social use

Raw Memory Ledger records, receipts, searches, and administration surfaces remain private to authorized founder/admin tooling.

Approved memory-aware conversational surfaces are different from raw Ledger administration. The target conversational surfaces are:

- one designated Wilhelmina server channel;
- direct conversations with Wilhelmina.

Within those approved surfaces, ordinary permitted social memories may be used across members when contextually relevant. This is intentionally the "full menace" social behavior: Wilhelmina is allowed to remember one person's ordinary social statement and later bring it up while talking with somebody else.

That permission does not override hard privacy classes. Credentials, financial data, exact private addresses, restricted/admin-only data, dangerous identifiers, diagnoses, and similar prohibited material are never comedy ammunition and must not enter ordinary chat context.

Gossip remains gossip. It must stay attributed and unverified rather than being presented as established fact.

## Server and DM behavior

### Designated server channel

Wilhelmina uses a selective social-predator participation style:

- direct mentions, replies, and direct questions receive a response;
- ordinary human conversation does not receive a mechanical response to every message;
- she may spontaneously interject only when there is something genuinely funny, useful, juicy, contradictory, or strongly relevant to contribute.

The later local selector/interjection gate should decide whether an ordinary message is worth considering before a chat-model call is made. The model may still return `NO_REPLY` for an optional interjection.

### DMs

DMs are a confessional-booth mode, not an amnesiac or sanitized version of the bot.

A user-initiated DM may use the same permitted Memory Ledger as server chat, including relevant cross-member context. The behavioral difference is social framing: DM replies may be more candid, detailed, intimate, and analytical because there is no public audience.

Wilhelmina does not proactively scrape third-party DMs and does not gain access to conversations she is not in.

## Categories and epistemic labels

Existing Memory Ledger categories remain schema-compatible:

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

Existing labels remain schema-compatible:

- `Fact`
- `Inference`
- `Impression`
- `Gossip`

Automatic extraction must prefer explicit durable statements over speculative person-level inference. The later extraction/privacy phase will define which inference/impression records may be machine-created under current platform policy. Schema compatibility alone is not authorization to generate psychological dossiers.

Gossip is treated as an attributed unverified claim, never established fact.

## Prohibited information

The deterministic local validator runs before any external AI request and before persistence.

At minimum, reject or quarantine:

- passwords and authentication secrets;
- API/access tokens and login credentials;
- banking, card, payment, or account information;
- government/private identity-document numbers;
- exact home/private addresses and precise live location;
- medical or mental-health diagnoses;
- intimate non-consensual material;
- information involving minors that is inappropriate for the adult-memory system;
- comparable dangerous private secrets.

Do **not** blanket-reject DMs merely because they are private. A DM sent directly to Wilhelmina is an eligible source after consent and policy checks. Private messages that were not sent to Wilhelmina are outside her accessible collection scope.

If local validation rejects a message, no external extraction request is made and no memory is created from that content.

## Memory ownership, records, and receipts

A stored memory is attached to the Coven Registry/profile shell of the participating member who supplied it. Third-party gossip does not automatically create a standalone outsider profile.

The existing schema-v6 record stores:

- guild ID;
- owner/subject user ID;
- category;
- epistemic label;
- concise summary;
- normalized duplicate key;
- normalized topic key;
- gossip marker;
- active status;
- creator ID;
- created, updated, and last-confirmed timestamps.

Nothing expires automatically under the existing persistence contract.

Every memory has at least one receipt.

A Discord receipt stores source message ID, jump URL when available, author, channel, timestamp, original excerpt, latest edited excerpt, edit timestamp, and source-deletion timestamp. DM receipts will use the same evidence principle without pretending a guild jump URL exists when Discord does not provide one.

An admin-authored memory uses an admin receipt and never fabricates Discord message metadata.

If a captured Discord source is later deleted, the existing design keeps the stored receipt excerpt and marks the source deleted.

## Duplicate, replacement, and contradiction rules

These decisions remain deterministic Python/SQLite behavior.

### Exact duplicate

Keep one memory record, add the new receipt, retain every supporting source, and update confirmation timestamps.

### Topic-scoped correction

For ordinary non-gossip memory, a newer correction about the same specific topic replaces that memory. The superseded content and receipts are permanently deleted. A minimal content-free replacement audit may remain.

Unrelated memories in the same category coexist.

### Contradictory gossip

Conflicting gossip remains as separate attributed claims. Related records are linked through contradiction rows. Deleting either memory removes the relevant contradiction relationship through cascading foreign keys.

The future chat layer may conversationally call out contradictions when both underlying memories are permitted in the current context.

## OpenAI boundary

OpenAI receives only context approved by deterministic local code for the current operation.

Python owns:

- guild/member authorization;
- consent and collection eligibility;
- prohibited-data filtering;
- reveal scope;
- identity/age calculation;
- duplicate/replacement decisions;
- contradiction links;
- database writes and deletes;
- context budgeting and local retrieval;
- logging/privacy policy.

OpenAI owns language tasks such as:

- structured candidate extraction from already-approved text;
- concise memory phrasing inside a strict schema;
- conversational reasoning over supplied context;
- Wilhelmina's prose and optional `NO_REPLY` judgement.

Model output is a proposal, never database authority.

Private memory/chat calls must use the shared asynchronous Responses API path with response storage disabled. Live private requests fail closed unless the deployment explicitly asserts an approved enhanced retention posture (`mam` or `zdr`). The provider-side MAM/ZDR setting is configured in the OpenAI project; an environment variable is only a runtime assertion and cannot grant the entitlement by itself.

Quality-first default routing is:

- GPT-5.6 Sol for Wilhelmina chat/general generation;
- GPT-5.6 Terra for structured memory work;
- model choices remain independently configurable and should later be validated with Wilhelmina-specific evals.

Operational logs may contain request IDs, model names, token counts, status/latency, and content-free internal identifiers. They must not contain raw prompts, model replies, memory summaries, receipts, preferred names, or birth dates.

## Full-profile and local retrieval contract

The current interlocutor's full permitted active profile remains core context for memory-aware chat. The later retrieval engine is not designed to amputate that profile to save pennies.

Local selection is primarily for:

- relevant memories belonging to other members;
- contradiction partners;
- detailed historical evidence;
- receipt snippets;
- especially relevant callbacks among a large history.

The planned selector will use deterministic local indexing/search and scoring. OpenAI is not asked to decide authorization or which private records it is allowed to retrieve.

## Persistent collection controls

The existing Memory Ledger stores persistent active/paused state and designated chat-channel configuration. Pause/resume survives process restarts and does not delete existing memories.

The later controls phase will reconcile those database settings with the new runtime collection policy. Runtime `off` or an unsatisfied ambient gate always wins over a permissive database setting.

## Administration

The planned founder/admin surface remains private/ephemeral where Discord permits it:

```text
/memory-admin status
/memory-admin pause
/memory-admin resume
/memory-admin set-chat-channel
/memory-admin profile
/memory-admin search
/memory-admin add
/memory-admin edit
/memory-admin delete
/memory-admin receipt
```

Any additional member data access/correction/deletion controls required by current platform terms will be implemented in the controls phase. The legacy `coven_profile_shells.memory_opt_out` field remains inert compatibility data unless explicitly migrated; it is not silently repurposed by Phase 1.

## Current schema status

### Memory Ledger schema version 6 — implemented

PR #33 implements:

- `memory_ledger_settings`;
- `memory_records`;
- `memory_receipts`;
- `memory_contradictions`;
- duplicate merging;
- permanent ordinary replacement;
- gossip contradiction links;
- admin and Discord receipts;
- permanent admin deletion with content-free audit;
- local prohibited-content validation;
- profile formatting and automated tests.

### Member identity schema version 8 — current stacked foundation

The identity foundation stores preferred name, full birth date, adult-memory consent timestamp, and the version of the disclosure accepted. Existing schema-v7 identity data migrates to a legacy consent version rather than receiving the richer disclosure automatically.

Because version 8 is now occupied by identity-consent migration, the next Memory Ledger schema expansion must use a later schema version.

## Future extraction contract

Automatic extraction is not yet implemented. When built, an eligible message may produce zero or more strict structured candidates such as:

```json
{
  "category": "Preference",
  "epistemic_label": "Fact",
  "summary": "Prefers iced coffee",
  "topic_key": "drink.preference.coffee.temperature",
  "relationship": "new|duplicate|replacement|contradictory_gossip",
  "existing_memory_id": null
}
```

Mandatory processing order:

1. classify the Discord source and interaction trigger;
2. reject bots/webhooks/empty text and disallowed collection modes;
3. verify current adult-memory consent and required local profile state;
4. enforce the ambient multi-key gate when the source is ambient;
5. run deterministic prohibited-information validation locally;
6. only then send allowed text plus bounded existing-memory context to the structured extractor;
7. validate the returned schema and local policy again;
8. let Python merge duplicates, perform topic-scoped replacement, or preserve/link contradictory gossip;
9. create the appropriate receipt transactionally.

Timeouts, refusals, malformed structured output, or provider failures create no speculative memory and do not block Discord event handling.

## Message edits and deletions

Edited sources preserve the original excerpt, store the latest excerpt/edit timestamp, run local validation before any re-extraction, and reconcile only memories connected to that source.

Deleted sources are marked deleted on matching receipts. The system does not reconstruct content it never captured.

## Seven-phase implementation order

### Phase 1 — Foundation reconciliation

- OpenAI Responses/async foundation made explicit and reviewable;
- quality-first workload model routing;
- private-call `store=false` enforcement and enhanced-retention fail-closed policy;
- versioned adult-memory consent and legacy migration;
- interaction/off/ambient runtime policy;
- three-key ambient activation gate;
- documentation/config/tests reconciled with DM and cross-member behavior.

### Phase 2 — Memory architecture upgrade

- next Memory Ledger schema migration;
- privacy/reveal metadata;
- entity indexing and local full-text search;
- deletion integrity and migration matrix;
- durable local structures needed by retrieval/extraction.

### Phase 3 — Memory controls

- full founder/admin Memory Ledger controls;
- required privacy/data-access/correction/deletion controls;
- persistent status/pause/resume/channel configuration;
- authorization and privacy tests.

### Phase 4 — Automatic memory extraction

- Discord event eligibility for approved interaction sources and DMs;
- local prohibited-data guard;
- strict OpenAI structured extraction;
- queue/backpressure/failure handling;
- new/edit/delete reconciliation;
- receipts, duplicate merging, replacement, and gossip contradiction handling.

### Phase 5 — Memory intelligence and context

- local FTS/index retrieval;
- deterministic scoring and contradiction expansion;
- full active speaker profile loading;
- cross-member memory selection;
- receipt/evidence budgeting;
- deterministic context assembly tests.

### Phase 6 — Wilhelmina chat brain

- designated server chat;
- fully memory-aware DM confessional mode;
- direct-response behavior;
- selective spontaneous interjection gate;
- cross-member social-memory use;
- adult Wilhelmina persona and chat evals.

### Phase 7 — Hardening and dormant ambient path

- adversarial/privacy regression suite;
- migration/reconnect/rate-limit testing;
- observability and rollback controls;
- production privacy assertions;
- ambient event path completed but kept disabled until all deployment/platform gates are satisfied.

## Final live testing

The live Discord pass must eventually verify consent migration, DMs with Wilhelmina, direct server interactions, bot/webhook exclusion, pause persistence, edits/deletes, duplicate merges, topic-scoped replacement, gossip contradiction links, full-profile loading, cross-member context rules, selective interjections, DM/server mode differences, private admin surfaces, enhanced OpenAI retention configuration, and the fact that ambient collection stays off when any required gate is absent.
