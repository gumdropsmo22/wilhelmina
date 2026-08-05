# Memory Ledger

The Memory Ledger is Wilhelmina's private, persistent record of what human members say in the home Discord server. It extends the Coven Registry profile shell without making member profiles public.

This document is the implementation contract for the Memory Ledger. Manual Discord testing remains deferred until the project's final live-testing pass.

## Product rules

### Collection scope

- Collection begins only after the feature is enabled. There is no history import or backfill.
- Wilhelmina may collect from any guild channel she can read.
- Direct messages are excluded.
- Only human-authored Discord messages are eligible.
- Bot messages, webhook messages, and automated integrations are ignored.
- Only message text is analyzed.
- Images, audio, video, uploaded files, and external-link contents are not inspected.
- Collection is silent.
- Collection is controlled globally by the founder/admin. There is no member-level opt-out in the approved design.
- The legacy `coven_profile_shells.memory_opt_out` column is inert compatibility data and must not alter collection.

### Ownership and visibility

- Each memory belongs to the Coven Registry profile of the human member who supplied it.
- Third-party gossip does not create a standalone profile for the person being discussed.
- Raw records, receipts, searches, status output, and administration commands are visible only to the founder/admin.
- Admin command responses must be ephemeral wherever Discord permits it.
- Memories may feed later approved Wilhelmina features without making the raw ledger public.

### Categories and labels

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

Gossip is presented internally as `Unverified gossip`. Accusations are stored as attributed claims, never established facts.

### Prohibited information

The Ledger must reject or redact the following before any external AI request and before persistence:

- passwords;
- access tokens and API keys;
- login credentials;
- exact residential addresses;
- banking or payment information;
- government or identity-document numbers;
- medical diagnoses;
- mental-health diagnoses;
- private-message content.

The future event listener must call the deterministic pre-extraction validator before sending text to the OpenAI extractor. If the validator rejects a message, no external request is made and no memory is created.

## Memory records

A memory record stores:

- guild ID;
- owner user ID linked to a Coven Registry profile shell;
- category;
- epistemic label;
- concise summary;
- normalized duplicate key;
- normalized topic key;
- gossip marker;
- active status;
- creator ID;
- created, updated, and last-confirmed timestamps.

Nothing expires automatically.

## Receipts

Every memory has at least one receipt.

### Discord receipt

A Discord-derived receipt stores:

- source kind `discord`;
- message ID;
- jump URL;
- author user ID;
- channel ID;
- original message timestamp;
- original excerpt;
- latest edited excerpt and edit timestamp when applicable;
- source-deletion timestamp when applicable.

### Admin receipt

An admin-authored memory uses source kind `admin` and stores:

- administrator user ID;
- the memory summary as the source excerpt;
- creation timestamp;
- no fabricated Discord message, channel, or jump URL.

If Discord later deletes a source message, its stored receipt remains and is marked deleted.

## Duplicate and contradiction behavior

### Duplicate memories

A repeated memory keeps one record, adds another receipt, preserves every supporting link, and updates `last_confirmed_at`.

### Ordinary replacement

For non-gossip records, a newer statement in the same replacement category permanently deletes the superseded record and its receipts before creating the new record.

A minimal `memory.replaced` audit event may remain, but it stores no deleted memory content.

### Gossip contradictions

Conflicting gossip remains as separate attributed claims. Records sharing a topic key are linked in `memory_contradictions`.

Both contradiction foreign keys use `ON DELETE CASCADE`, so permanently deleting either memory also removes the relationship row.

Future chat behavior:

- contradictions observed inside the designated Wilhelmina chat may be called out immediately;
- contradictions observed elsewhere are stored silently and may be raised later in the designated chat;
- dialogue should sound conversational and messy rather than judicial.

## Collection controls

The Ledger stores a persistent guild-level state:

- active;
- paused.

Admin controls will support pause, resume, status, and designated-chat-channel configuration. The state survives process restarts and Discord reconnections. Pausing does not delete existing memories.

## Designated Wilhelmina chat channel

Exactly one guild channel may be configured as Wilhelmina's conversation channel.

- Collection may occur in every readable guild channel.
- Open use of memories is limited to the designated Wilhelmina chat channel.
- Outside that channel, Wilhelmina may collect but must not reveal memories.
- The full active profile is loaded for future Wilhelmina chat responses.

## Administration surface

The planned founder/admin-only command group is `/memory-admin`:

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

All responses are private/ephemeral where Discord permits it.

## SQLite schema version 6

### `memory_ledger_settings`

Stores guild collection state and the designated Wilhelmina channel.

### `memory_records`

Stores memory content and links `(guild_id, subject_user_id)` to `coven_profile_shells` with cascade deletion.

### `memory_receipts`

Stores either a `discord` source or an `admin` source. Receipts cascade when their memory is deleted.

### `memory_contradictions`

Stores normalized unordered gossip-memory pairs. Both memory references cascade on deletion.

`initialize_memory_schema()` initializes its Coven Registry dependency first, applies all Memory Ledger tables and indexes idempotently, and records schema version 6.

## Extraction contract

Automatic extraction is a later tranche and will require strict structured output. One message may yield zero or more candidates:

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

Processing order is mandatory:

1. reject DMs, bots, webhooks, empty text, and paused guilds;
2. confirm a Coven Registry profile shell exists;
3. run deterministic prohibited-information validation locally;
4. only then send allowed text and current profile context to the extractor;
5. validate the returned structure;
6. merge duplicates, permanently replace ordinary memories, or preserve/link gossip contradictions;
7. create the appropriate receipt.

AI failure never blocks Discord event handling. Failed extraction creates no speculative memory.

## Message edits and deletions

### Edited message

- preserve the original excerpt;
- store the latest excerpt and edit timestamp;
- validate the edited text before any future re-extraction;
- reconcile only records connected to that source message.

### Deleted message

- mark matching Discord receipts as source deleted;
- keep stored excerpts and memories;
- do not reconstruct content that was never captured.

## Build status and order

### Phase 1 — Persistence foundation

Implemented in PR #33:

- schema version 6;
- settings, records, receipts, and contradiction relationships;
- duplicate merging;
- permanent ordinary replacement;
- gossip preservation and contradiction links;
- admin and Discord receipt variants;
- permanent deletion with content-free audit events;
- pre-extraction prohibited-content validation;
- profile rendering;
- automated tests.

### Phase 2 — Admin controls

- feature flag;
- ephemeral `/memory-admin` commands;
- status, pause, resume, channel, profile, search, add, edit, delete, and receipt operations;
- founder/admin authorization tests;
- README and `.env.example` updates.

### Phase 3 — Automatic collection

- Message Content Intent when enabled;
- shared OpenAI client and strict extractor;
- new, edit, and delete message listeners;
- human/guild/text-only filters;
- pre-AI prohibited-data filtering;
- failure logging and rate controls.

### Phase 4 — Open-chat bridge

- full active-profile loading;
- one-channel reveal boundary;
- immediate and deferred contradiction behavior;
- Wilhelmina's conversational response generation.

## Deferred live testing

The final Discord pass must verify Message Content Intent, collection from multiple channels, bot/webhook exclusion, private admin responses, pause persistence, edited/deleted receipts, duplicate merges, permanent replacement, gossip contradiction links, designated-channel reveal boundaries, and full-profile loading.
