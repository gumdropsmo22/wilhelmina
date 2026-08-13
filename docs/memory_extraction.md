# Automatic Memory Extraction — Phase 4

## Purpose

Phase 4 turns eligible conversations involving Wilhelmina into typed Memory Ledger proposals without giving the model authority over authorization or SQLite.

The pipeline is deliberately narrow:

```txt
Discord human text
  -> local eligibility gates
  -> local sensitive-data guard
  -> durable SQLite queue
  -> private OpenAI structured extraction
  -> deterministic Python validation
  -> deterministic Memory Ledger reconciliation
```

SQLite remains canonical. OpenAI proposes candidates only.

## Runtime gates

Automatic extraction requires all of the following:

1. `ENABLE_MEMORY_EXTRACTION=true` so `cogs.memory_extraction` is loaded.
2. `MEMORY_COLLECTION_MODE=interaction` (or `ambient`, which still behaves interaction-only in Phase 4).
3. The persistent Memory Ledger collection gate is resumed.
4. The author has the current versioned adult-memory consent.
5. A usable OpenAI API runtime exists.
6. `OPENAI_RETENTION_MODE=mam` or `zdr` is asserted for the deployment and actually configured in the OpenAI project.

If any gate fails, private content does not enter OpenAI extraction.

`ENABLE_MEMORY_EXTRACTION` defaults to `false`. Enabling it also requests Discord's Message Content gateway intent. Configure that intent in the Discord Developer Portal before enabling the feature in a deployment.

## Eligible Discord text

Phase 4 collects only human-authored text in the dedicated home server context:

- a direct DM sent to Wilhelmina;
- a human message in the designated Wilhelmina chat channel;
- a guild message that mentions Wilhelmina;
- a guild reply whose resolved referenced message was authored by Wilhelmina.

Bots, webhooks, empty/non-text messages, other guilds, missing/legacy consent, and paused/off collection are rejected locally.

Attachments, media, embeds, files, and external-link contents are not read by the extractor. Only the message's own text enters the pipeline.

### Ambient collection remains dormant

Even if all future ambient environment gates are set, Phase 4 still rejects unaddressed guild chatter outside the designated Wilhelmina channel. Whole-server ears remain a later approved tranche.

## Sensitive-data guard

`services.memory_extraction.guard_extractable_text()` runs before queue persistence and before an OpenAI request. It composes the Memory Ledger guard with extra local detection for common token formats, government-ID patterns, exact street-address shapes, and Luhn-valid payment-card numbers.

Blocked content is not enqueued and is not sent to OpenAI.

The model output is checked by the same guard again before any memory mutation. A model cannot reintroduce prohibited content through its summary.

## Durable queue

Schema version 10 adds `memory_extraction_jobs`.

One row represents the latest known version of one Discord source message. The unique key is `(guild_id, source_context, message_id)`.

States:

- `pending`
- `processing`
- `retry`
- `completed`
- `rejected`
- `failed`

The queue stores source text only while work is outstanding. Completed, rejected, terminally failed, and source-deleted jobs clear the queued text. A SHA-256 content hash supports idempotency and prevents stale provider results from overwriting a newer edit.

Processing leases recover jobs after an interrupted worker. Provider/apply failures retry with bounded exponential backoff and become terminal after four attempts.

## Structured OpenAI extraction

`services.memory_extraction_provider` reuses the shared async client and `private_ai_config(workload="memory")` from `services.ai`.

Requests use the Responses API with:

- the configured memory model;
- strict JSON Schema structured output;
- `store=False`;
- native async calls;
- the existing timeout/retry policy.

Operational logs may contain model, request ID, token counts, error class/status, job/message IDs, and gate reasons. They do not contain prompts, message text, memory summaries, preferred names, dates of birth, or receipts.

## Proposal contract

The model may return at most six candidates. Each candidate contains:

- category;
- epistemic label;
- summary;
- stable topic key;
- importance `0..100`;
- confidence `0..100`;
- bounded `member` or `term` entities.

Automatic extraction cannot create `Admin note` records.

A `Gossip` category or label is normalized to both `Gossip`. Third-party claims therefore remain attached to the speaking member and unverified.

Member entity IDs are accepted only when the source message explicitly mentioned those IDs. Python rejects invented member links.

Candidates below confidence 70 are ignored rather than persisted.

## Deterministic reconciliation

`services.memory_reconciliation` is the mutation authority for extractor proposals.

Every accepted candidate goes through existing Memory Ledger APIs, preserving the already-reviewed rules:

- exact duplicate -> merge receipt;
- ordinary same-topic correction -> replace superseded memory;
- unrelated memory -> coexist;
- gossip contradiction -> coexist and link;
- automatic memories -> `ordinary/cross_member` only;
- model output never chooses authorization or destructive behavior.

When an edited source changes what should be remembered, obsolete source receipts are detached. A memory left with zero evidence is deleted. If other receipts still support it, the memory survives.

### Edited-source evidence

Edits preserve both versions:

- `original_excerpt` keeps the first wording;
- `edited_excerpt` keeps the latest processed wording;
- `source_edited_at` marks the edit.

If a correction replaces the old memory record, reconciliation transfers the original source wording onto the corrected record's receipt before the obsolete record is removed.

### Deleted sources

Discord deletion events do not erase the receipt. They set `source_deleted_at`, preserving the previously captured evidence as required by the Memory Ledger contract. Any outstanding queued source text is cleared.

## Failure behavior

The feature fails closed:

- missing current consent -> no queue;
- collection off/paused -> no queue;
- private OpenAI retention gate unavailable -> no queue;
- sensitive source -> no queue;
- provider outage after enqueue -> retry;
- invalid structured proposal -> reject without mutation;
- edited message wins over stale in-flight provider response through content-hash comparison;
- source deletion clears queued text and marks existing receipts deleted.

## Deployment / rollback

Phase 4 can be deployed inertly with:

```env
ENABLE_MEMORY_EXTRACTION=false
MEMORY_COLLECTION_MODE=off
OPENAI_RETENTION_MODE=standard
```

To roll back collection immediately without changing code, set either:

```env
MEMORY_COLLECTION_MODE=off
```

or use `/memory-admin pause`.

To unload the event worker and stop requesting Message Content intent, set:

```env
ENABLE_MEMORY_EXTRACTION=false
```

Existing Memory Ledger records and receipts are preserved by all three rollback paths.

## Testing

CI uses mocked OpenAI calls only. No real API key is required.

Regression coverage includes:

- schema v10 and idempotent queue initialization;
- pre-AI sensitive-data rejection;
- idempotent enqueue/edit requeue;
- retries and terminal text clearing;
- strict proposal validation;
- gossip normalization and confidence threshold;
- deterministic memory/receipt/entity creation;
- same-topic edit correction with original/latest evidence preservation;
- source deletion handling;
- consent/runtime/pause/home-guild/interaction eligibility;
- ambient-mode non-activation;
- strict provider schema + `store=False` request shape;
- least-privilege Message Content intent configuration.
