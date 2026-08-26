# Automatic Memory Extraction — Phase 4

## Purpose

Phase 4 turns eligible conversations involving Wilhelmina into typed Memory Ledger proposals without giving the model authority over authorization or SQLite.

The pipeline is deliberately narrow:

```txt
Discord human text
  -> local eligibility gates
  -> local dangerous-secret guard
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
4. The author has a completed private identity profile.
5. A usable OpenAI API runtime exists.
6. `OPENAI_RETENTION_MODE=mam` or `zdr` is asserted for the deployment and actually configured in the OpenAI project.

If any gate fails, private content does not enter OpenAI extraction.

`ENABLE_MEMORY_EXTRACTION` defaults to `false`. Enabling it also requests Discord's Message Content gateway intent. Configure that intent in the Discord Developer Portal before enabling the feature in a deployment.

Mutable authorization is checked more than once. The event path re-checks home guild, runtime mode, persistent pause/resume state, member profile state, and interaction scope inside a SQLite `BEGIN IMMEDIATE` transaction immediately before queue persistence. A claimed job re-checks authorization immediately before the provider request and again inside a write transaction immediately before any Memory Ledger mutation.

The old `profile_has_current_consent(...)` helper name remains only as a compatibility alias for the already-reviewed Phase-4 worker. It now delegates to profile-state eligibility and does **not** inspect `adult_memory_consent_at` or `memory_consent_version`. Those schema-v8 columns are non-authoritative compatibility data pending the later physical migration.

## Eligible Discord text

Phase 4 collects only human-authored text in the dedicated home server context:

- a direct DM sent to Wilhelmina;
- a human message in the designated Wilhelmina chat channel;
- a guild message that mentions Wilhelmina;
- a guild reply whose resolved referenced message was authored by Wilhelmina.

Bots, webhooks, empty/non-text messages, other guilds, missing identity profiles, and paused/off collection are rejected locally.

Attachments, media, embeds, files, and external-link contents are not read by the extractor. Only the message's own text enters the pipeline.

### Ambient collection remains dormant

Even if all future ambient environment gates are set, Phase 4 still rejects unaddressed guild chatter outside the designated Wilhelmina channel. Whole-server ears remain a later approved tranche.

## Dangerous-secret guard

`services.memory_extraction.guard_extractable_text()` runs before queue persistence and before an OpenAI request. It composes the Memory Ledger guard with deterministic local detection for credentials/secrets, common provider token forms, government/private identifiers, exact street-address shapes, and Luhn-valid payment-card numbers.

The guard covers recognizable secret formats and labelled forms such as access keys, secret access keys, client secrets, private tokens, passports, national IDs, driver licenses, and comparable identifiers. It does **not** reject content merely because the subject matter is medical, mental-health related, sexual between adults, romantic, political, religious, identity-related, substance-related, embarrassing, rude, or otherwise socially sensitive.

Blocked dangerous-secret content is not enqueued and is not sent to OpenAI.

Every model-controlled persisted string is checked again after structured extraction. Summary text, raw topic keys, and term entity keys all pass through the same dangerous-secret guard before normalization or Memory Ledger mutation. A model cannot smuggle a credential, private identifier, payment secret, or doxxing-grade address into metadata after the source text passed inspection.

### Raw message edits

Raw Discord edit events are authoritative because they fire even when the original message is not present in discord.py's cache.

For a known source message, one `BEGIN IMMEDIATE` transaction performs the edit lifecycle:

1. normalize and compare the Discord edit timestamp;
2. ignore an older/equal edit if a newer edit version is already recorded;
3. cancel outstanding queue work and advance the content-free edit version;
4. re-check runtime/pause/home-guild/profile-state authorization;
5. only after authorization, inspect the new text with the dangerous-secret guard;
6. update receipt edit text only when authorized;
7. requeue the newest safe version only when current interaction scope and provider gates still pass.

This ordering prevents an unauthorized edit from writing new raw text into receipts and prevents two bot processes from letting a late older edit overwrite a newer queued version.

If an authorized edit trips the dangerous-secret guard, the raw secret text is not queued or copied into the receipt. The receipt stores only:

```txt
[edited content withheld by sensitive-data guard]
```

If a raw update cannot provide inspectable/versioned edit data, outstanding extraction work is cancelled fail-closed rather than guessed.

## Durable queue

Schema version 11 owns `memory_extraction_jobs`.

One row represents the latest known version of one Discord source message. The unique key is `(guild_id, source_context, message_id)`.

States:

- `pending`
- `processing`
- `retry`
- `completed`
- `rejected`
- `failed`

The queue stores source text only while work is outstanding. Completed, rejected, terminally failed, edited-away, and source-deleted jobs clear queued text.

### Claim ownership

Every transition into `processing` receives a cryptographically random `claim_token`. Completion, rejection, retry, and failure transitions require the exact job ID plus the exact current claim token. Content hash alone is not considered ownership.

If a lease expires, its token is revoked before the job can be reclaimed. Claims below `MAX_ATTEMPTS` return to `retry`; an expired claim that has already reached `MAX_ATTEMPTS` becomes terminal `failed`, clears its raw source text, and cannot be reclaimed again. The ready-job selector also refuses rows whose attempt counter has already reached the cap. A slow provider call therefore cannot create an unbounded stale-lease retry loop until the raw-text TTL.

A stale provider response from claim A cannot mutate or finish work after claim B owns the row.

Fresh v11 databases also enforce `processing -> claim_token IS NOT NULL` at the table level. Migrated v10 databases install equivalent SQLite triggers so an older v10 worker cannot create a new tokenless processing claim during deployment overlap.

### v10 -> v11 deployment transition

A v10 row already marked `processing` has no trustworthy claim generation. During v11 schema initialization, every such tokenless processing row is fail-closed:

- status becomes `rejected`;
- transient source text is erased;
- the lease is cleared;
- the error code becomes `claim_migration_invalidated`.

The v11 trigger then rejects any later old-style attempt to mark a row `processing` without a token. Deployments should still stop/drain old v10 bot processes before enabling the v11 worker; the database enforcement exists as a second safety boundary rather than permission to intentionally run mixed versions indefinitely.

### Transient raw-text lifetime

Outstanding source text is transient queue material, not canonical memory. `services.memory_extraction_retention` enforces a one-hour absolute lifetime for raw source text. Retry bookkeeping and provider processing do not extend that window. Initial messages age from queue insertion; a genuine Discord edit resets the clock from the newest accepted source edit timestamp.

Retention runs independently from the provider worker as well as during normal worker passes. A provider coroutine therefore cannot hold raw source text past the TTL by remaining in `processing`.

The worker also performs an expiry sweep inside the final `BEGIN IMMEDIATE` transaction after the provider returns and before proposal reconciliation. When a processing row expires, its content and claim token are cleared. Any subsequently returned provider result fails current-row/ownership validation and is discarded without creating memory or receipts.

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
- `claim_subject`, either `author` or `third_party`;
- `claim_attribution`, either `self` or `author_report`;
- summary;
- stable topic key;
- importance `0..100`;
- confidence `0..100`;
- bounded `member` or `term` entities.

The two claim fields are not decorative model prose. Python accepts only the pairs `author/self` and `third_party/author_report`. Missing or contradictory attribution metadata makes the proposal invalid.

Automatic extraction cannot create `Admin note` records.

Any candidate marked `third_party/author_report` is deterministically forced to both category `Gossip` and epistemic label `Gossip`, even if the model proposed `Fact`, `Inference`, or `Impression`. A model therefore cannot turn a third-party report into ordinary asserted memory by choosing a stronger label. The stored Memory Ledger subject remains the speaking member, preserving who supplied the report; Gossip remains attributed and unverified.

A `Gossip` category or label is likewise normalized to both `Gossip`.

Member entity IDs are accepted only when the source message explicitly mentioned those IDs. Python rejects invented member links.

Candidates below confidence 70 are ignored rather than persisted.

A single proposal cannot contain multiple accepted ordinary memories for the same normalized topic. That conflict is rejected during a preflight pass before any Memory Ledger mutation. Gossip is exempt because conflicting attributed gossip is intentionally allowed to coexist.

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

Edits preserve both versions only when current authorization still permits receipt maintenance and the latest text is safe to retain:

- `original_excerpt` keeps the first wording;
- `edited_excerpt` keeps the latest authorized processed wording;
- `source_edited_at` marks the edit.

The queue separately advances its content-free edit timestamp even when a newer edit cannot be retained. That timestamp is used only to stop a stale older handler from resurrecting old text.

### Deleted sources

Discord deletion events do not erase the receipt. They set `source_deleted_at`, preserving previously captured evidence as required by the Memory Ledger contract. Any outstanding queued source text is cleared and outstanding work becomes terminal.

## Failure behavior

The feature fails closed:

- missing completed identity profile -> no queue;
- collection off/paused -> no queue;
- private OpenAI retention gate unavailable -> no queue;
- dangerous-secret source -> no queue;
- unauthorized edit -> outstanding job cancelled, edit version advanced, no new receipt text persisted;
- dangerous-secret authorized edit -> outstanding job cancelled, secret not persisted, receipt gets only the safe marker;
- stale older raw edit -> ignored without overwriting newer queue/receipt state;
- queued job loses profile/pause/runtime authorization before provider -> reject before provider;
- authorization changes while provider is running -> reject before mutation;
- provider outage after enqueue -> retry;
- expired lease below the attempt cap -> revoke claim token before retry/reclaim;
- expired lease at the attempt cap -> terminal failure and raw-text erasure;
- unprocessed or in-flight raw source text older than one hour -> reject, erase text, revoke claim;
- missing/invalid claim-subject attribution -> reject without mutation;
- third-party report proposed with a stronger epistemic label -> force to attributed/unverified Gossip;
- invalid structured proposal -> reject without mutation;
- dangerous secret in model-controlled metadata -> reject without mutation;
- conflicting ordinary same-topic candidates -> reject during preflight before mutation;
- source deletion clears queued text and marks existing receipts deleted.

Health, mental-health, adult relationship/sexual, political, religious, identity, substance-use, embarrassing, gossip, and other socially sensitive material is not a failure condition merely because of its subject category.

## Deployment / rollback

Phase 4 can be deployed inertly with:

```env
ENABLE_MEMORY_EXTRACTION=false
MEMORY_COLLECTION_MODE=off
OPENAI_RETENTION_MODE=standard
```

For the v10 -> v11 rollout:

1. stop or drain old v10 bot workers;
2. deploy v11 code with extraction still disabled/off;
3. allow schema initialization to invalidate any leftover tokenless processing rows and install claim-token enforcement triggers;
4. verify migrations/CI/runtime diagnostics;
5. enable the intended interaction collection runtime only after the deployment's MAM/ZDR and Discord intent prerequisites are configured.

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

- schema v11 initialization and v10 -> v11 migration;
- legacy tokenless processing-claim invalidation and old-style claim rejection;
- permissiveness regressions for medical/mental-health/adult/socially sensitive subject matter;
- pre-AI credential/private-ID/payment/address rejection;
- post-model summary/topic/entity dangerous-secret rejection;
- idempotent enqueue/edit requeue;
- exact claim-token ownership across lease expiry/reclaim;
- stale-lease attempt-cap terminalization with raw-text erasure;
- bounded retries and terminal text clearing;
- absolute raw-text retention for pending, retry, and in-flight processing rows;
- full worker-path provider-return-after-TTL rejection with zero memory/receipt mutation;
- uncached/raw dangerous-secret edit cancellation;
- unauthorized edit cancellation without receipt-text persistence;
- out-of-order rapid edit versioning where the newest edit wins;
- strict proposal validation including claim subject/attribution pairs;
- deterministic third-party-claim coercion to Gossip;
- preflight same-topic conflict rejection before mutation;
- gossip normalization and confidence threshold;
- deterministic memory/receipt/entity creation;
- source deletion handling;
- atomic mutable authorization re-check at enqueue and before mutation;
- profile/runtime/pause/home-guild/interaction eligibility;
- ambient-mode non-activation;
- strict provider schema + `store=False` request shape;
- least-privilege Message Content intent configuration.
