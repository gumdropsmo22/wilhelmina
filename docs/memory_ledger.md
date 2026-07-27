# Memory Ledger

The Memory Ledger is Wilhelmina's private, persistent record of what human members say in the home Discord server. It extends the Coven Registry profile shell without making member profiles public.

This document is the implementation contract for the first Memory Ledger build. Manual Discord testing remains deferred until the project's final live-testing pass.

## Product rules

### Collection scope

- Collection begins only after the feature is enabled. There is no history import or backfill.
- Wilhelmina may collect from any guild channel she can read.
- Direct messages are excluded.
- Only human-authored Discord messages are eligible.
- Bot messages, webhook messages, and automated integration output are ignored.
- Only message text is analyzed.
- Images, audio, video, uploaded files, and the contents of external links are not inspected.
- Collection is silent. Wilhelmina does not react, reply, or notify members when a memory is saved.

### Ownership and visibility

- Each memory belongs to the Coven Registry profile of the human member who supplied it.
- Third-party gossip does not create a standalone profile for the person being discussed. It remains attached to the member who submitted it.
- Raw Memory Ledger records, receipts, searches, status output, and administration commands are visible only to the founder/admin.
- Admin command responses must be ephemeral wherever Discord permits it.
- Memories may later feed approved Wilhelmina features, but that does not make the raw ledger public.

### Categories

The initial category set is:

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

Every automatically extracted record also carries one epistemic label:

- `Fact`
- `Inference`
- `Impression`
- `Gossip`

Gossip must be presented internally as `Unverified gossip`. Accusations are stored as attributed claims, never as established facts.

### Information that must never be saved

The Ledger must reject or redact:

- passwords;
- access tokens;
- login credentials;
- exact residential addresses;
- banking or payment information;
- government or identity-document numbers;
- medical diagnoses;
- mental-health diagnoses;
- private-message content.

Explicit self-identification, reclaimed in-group language, inferred traits, gossip, accusations, and third-party information are otherwise allowed under the rules above.

## Memory records

A memory record stores:

- guild ID;
- owner user ID;
- Coven Mark linkage;
- category;
- epistemic label;
- concise summary;
- normalized topic key for duplicate and contradiction handling;
- optional subject text for gossip or relationship context;
- active status;
- first-seen timestamp;
- last-confirmed timestamp;
- created and updated timestamps.

The active profile is permanent until an administrator edits, replaces, or deletes a record. Nothing expires automatically.

## Receipts

Every memory must have at least one receipt. A receipt stores:

- message ID;
- Discord jump URL;
- author user ID;
- channel ID;
- original message timestamp;
- original excerpt;
- latest edited excerpt;
- edit timestamp when applicable;
- whether the source message was later deleted;
- receipt creation and update timestamps.

The Ledger preserves the original excerpt and the edited excerpt. If Discord later deletes the source message, the receipt remains and is marked `source deleted`.

## Duplicate and contradiction behavior

### Duplicate memories

When a new message repeats an existing memory:

- keep one memory record;
- add the new receipt;
- preserve all supporting message links;
- update `last_confirmed_at`;
- do not create a second copy.

### Normal contradictions

For non-gossip records, a newer statement replaces the older active memory. The older memory content is permanently deleted. A minimal audit event may record that a replacement occurred, but it must not preserve the deleted content.

### Gossip contradictions

Conflicting gossip from different speakers remains as separate, attributed claims. Records sharing a topic key may be linked as contradictory without merging their claims.

Wilhelmina's future chat behavior is intentionally less formal than the storage model:

- if the contradiction occurs inside the designated Wilhelmina chat channel, she may call it out immediately;
- if it occurs elsewhere, she stores it silently and may bring it up the next time the subject appears in the designated chat channel;
- dialogue should sound conversational, messy, and instigating rather than like a tribunal or case-management system.

## Collection controls

The Ledger has a persistent guild-level state:

- `active`;
- `paused`.

Admin controls must support:

- pause collection;
- resume collection;
- report current status.

The state survives process restarts and Discord reconnections. Pausing collection does not delete or alter existing memories.

## Designated Wilhelmina chat channel

Exactly one guild channel may be configured as Wilhelmina's conversation channel.

- The Ledger collects from every readable guild channel.
- Open use of memories is limited to the designated Wilhelmina chat channel.
- Outside that channel, Wilhelmina may collect memories but must not reveal or weaponize them in conversation.
- The full active profile for participating members is loaded for every future Wilhelmina chat response.
- No profile compression or artificial limit is planned for the initial single-digit, low-activity server.
- A technical overflow safeguard may be added later only if model context limits are reached.

## Administration surface

The first command group should be `/memory-admin` and remain founder/admin only.

Recommended commands:

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

Expected behavior:

- `status` reports collection state, configured chat channel, record count, receipt count, and last collection error.
- `profile` shows the full active memory file for one member.
- `search` filters by member, category, label, subject, or text.
- `add` creates an admin-authored record with an `Admin note` default category unless another category is chosen.
- `edit` may change category, label, summary, subject, and normalized topic.
- `delete` permanently erases the memory and its receipts, leaving only a content-free audit event.
- `receipt` displays the stored source excerpt and jump link.

## Proposed SQLite schema

The implementation should add schema version 6 and create the following tables.

### `memory_ledger_settings`

- `guild_id` primary key;
- `collection_enabled` boolean, default true;
- `chat_channel_id` nullable;
- `last_error_code` nullable;
- `last_error_at` nullable;
- `created_at`;
- `updated_at`.

### `memory_records`

- `id` integer primary key;
- `guild_id`;
- `owner_user_id`;
- `category`;
- `epistemic_label`;
- `summary`;
- `topic_key`;
- `subject_text` nullable;
- `is_active` boolean;
- `first_seen_at`;
- `last_confirmed_at`;
- `created_at`;
- `updated_at`;
- foreign key to `coven_profile_shells (guild_id, user_id)` with cascade deletion;
- unique active duplicate key scoped to guild, owner, category, epistemic label, and topic key.

### `memory_receipts`

- `id` integer primary key;
- `memory_id` foreign key with cascade deletion;
- `guild_id`;
- `message_id`;
- `channel_id`;
- `author_user_id`;
- `jump_url`;
- `source_created_at`;
- `source_edited_at` nullable;
- `original_excerpt`;
- `latest_excerpt`;
- `source_deleted` boolean;
- `created_at`;
- `updated_at`;
- unique key on memory ID and message ID.

### `memory_contradictions`

- `id` integer primary key;
- `guild_id`;
- `left_memory_id`;
- `right_memory_id`;
- `topic_key`;
- `created_at`;
- unique unordered pair constraint enforced by normalized IDs in service code.

## Extraction contract

Automatic extraction should use the existing AI service asynchronously and require strict JSON output. One Discord message may yield zero or more candidates.

Each candidate must contain:

```json
{
  "category": "Preference",
  "epistemic_label": "Fact",
  "summary": "Prefers iced coffee",
  "topic_key": "drink.preference.coffee.temperature",
  "subject_text": null,
  "relationship": "new|duplicate|replacement|contradictory_gossip",
  "existing_memory_id": null
}
```

Before persistence, deterministic validation must:

- reject unknown categories and labels;
- reject empty summaries or topic keys;
- enforce length limits;
- block prohibited information;
- ensure gossip is labeled as gossip;
- ensure accusations are phrased as attributed claims;
- ignore AI output that cannot be parsed safely.

AI failure must never block Discord event handling. On extraction failure, the message is skipped, an operational error is logged, and no speculative memory is created.

## Message-event flow

### New message

1. Reject DMs, bots, webhooks, empty text, and disabled or paused guilds.
2. Confirm the author has a Coven Registry entry and profile shell.
3. Send text plus the author's current active profile to the extractor.
4. Validate candidates deterministically.
5. Merge duplicates, replace normal contradictions, or preserve contradictory gossip.
6. Create receipts and write content-free audit events for admin mutations or permanent deletion.

### Edited message

1. Locate receipts by message ID.
2. Preserve the original excerpt.
3. Update the latest excerpt and edit timestamp.
4. Re-run extraction against the edited text.
5. Reconcile memories created from that message without erasing receipts from unrelated messages.

### Deleted message

1. Locate receipts by message ID.
2. Mark them `source_deleted = true`.
3. Keep the stored excerpts and memory records.
4. Do not attempt to reconstruct content that was never captured.

## Prompt-loading interface

The Ledger service should expose a deterministic formatter for future open chat, for example:

```python
render_full_profile_context(connection, guild_id=..., user_ids=[...]) -> str
```

The formatter should include categories, labels, summaries, subjects, confirmation dates, and contradiction markers. It should not include raw receipts unless a future prompt explicitly needs them.

Open-chat integration is a later feature. The Memory Ledger build should provide the interface without inventing the chat system inside this PR.

## Build order

### Phase 1 — Persistence foundation

- schema version 6;
- settings, record, receipt, and contradiction dataclasses;
- CRUD and query service;
- duplicate merge;
- normal replacement;
- gossip contradiction preservation;
- permanent deletion with content-free audit event;
- profile-context formatter;
- unit tests.

### Phase 2 — Admin controls

- feature flag;
- ephemeral `/memory-admin` group;
- status, pause, resume, channel, profile, search, add, edit, delete, and receipt commands;
- founder/admin authorization tests;
- documentation and environment updates.

### Phase 3 — Automatic collection

- message-content intent when the feature is enabled;
- AI extraction prompt and strict parser;
- new-message listener;
- edit and delete listeners;
- bot/webhook/DM/text-only filters;
- failure logging and rate-control tests.

### Phase 4 — Open-chat bridge

- load the full active profile for relevant participants;
- enforce the one-channel reveal boundary;
- immediate contradiction callouts inside the chat channel;
- deferred contradiction use when contradictions are observed elsewhere;
- conversational Wilhelmina behavior rather than formal dispute language.

## Test requirements

The automated suite must cover at least:

- idempotent schema initialization;
- persistent pause/resume state;
- no history-import path;
- human-only and guild-only filters;
- duplicate merge with multiple receipts;
- newer normal memory replacing older content;
- contradictory gossip remaining separate and attributed;
- edited receipt preserving original and latest excerpts;
- deleted source retaining excerpts and marking deletion;
- permanent admin deletion removing records and receipts;
- content-free audit deletion event;
- prohibited-information rejection;
- admin-only ephemeral command behavior;
- full-profile prompt formatting;
- collection from readable channels while reveal remains restricted to the designated chat channel.

## Deferred live testing

The final Discord pass must verify privileged Message Content Intent configuration, collection from multiple readable channels, bot/webhook exclusion, ephemeral admin responses, pause persistence across restart and reconnection, edited/deleted receipt handling, duplicate merges, contradiction behavior, designated-channel reveal boundaries, and full-profile loading in live Wilhelmina chat.
