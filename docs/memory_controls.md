# Memory Ledger Controls

Phase 3 adds the private founder/admin command surface for the Memory Ledger. The feature is implemented by `cogs.memory_admin` over the existing schema-v9 persistence APIs. It does not call OpenAI and does not require an API key.

## Authorization and privacy

`/memory-admin` is:

- guild-only;
- restricted to Discord administrators through default command permissions and a runtime permission check;
- restricted to Wilhelmina's configured `HOME_GUILD_ID`;
- ephemeral for every response;
- allowed to show `admin_only` and restricted records because it is the trusted private administration surface.

Normal members do not receive a Memory Ledger browsing command. Public Registry behavior remains separate.

## Persistent controls

`/memory-admin status` reports the local persistent collection gate, deployment runtime collection policy, designated Wilhelmina channel, content-free record counts, and Memory Ledger integrity checks.

`/memory-admin pause` and `/memory-admin resume` persist `memory_ledger_settings.collection_enabled`. Pausing does not delete existing memories. Resuming does not override `MEMORY_COLLECTION_MODE`; the persistent database gate and the deployment runtime policy remain independent checks.

`/memory-admin set-channel` and `/memory-admin clear-channel` persist the designated memory-aware Wilhelmina server channel for later chat phases.

## Private inspection

The founder/admin surface supports:

- `/memory-admin profile` — paginated full active member profile, including private identity context when available;
- `/memory-admin show` — one Memory Ledger record by ID;
- `/memory-admin receipts` — paginated source evidence for a record;
- `/memory-admin search` — local FTS search with deterministic reveal-scope filters;
- `/memory-admin member-data` — content-free Memory Ledger inventory for a current member;
- `/memory-admin member-data-id` — the same inventory for a departed/archived member by Discord user ID.

Member inventory includes both memories whose subject is that member and receipts authored by that member on somebody else's memory. Cross-subject authored receipts are counted separately so they are not silently missed or double-counted.

Admin search may intentionally include every reveal scope. This does not change the normal chat retrieval defaults and does not make `admin_only` records socially revealable.

## Manual mutation

The founder/admin surface supports:

- `/memory-admin add` — admin-authored memory with an honest `admin` receipt;
- `/memory-admin edit` — deterministic local correction of record fields;
- `/memory-admin delete` — permanent deletion of one record and dependent receipts/entities/contradiction/search rows;
- `/memory-admin delete-member` — permanent Memory Ledger purge for a current member;
- `/memory-admin delete-member-id` — the same purge for a departed/archived member by Discord user ID.

Single-record deletion requires the exact confirmation text `DELETE`.

Member-wide Memory Ledger deletion requires the exact confirmation text `DELETE MEMBER`.

### Duplicate admin writes

Exact duplicates still merge receipts rather than creating another record. If the new admin write requests a narrower privacy posture, the stored duplicate is tightened deterministically. Privacy/reveal metadata may tighten but never loosen:

- `ordinary/cross_member` can become `restricted/admin_only` when a later duplicate requires it;
- an already restricted/admin-only duplicate cannot be reopened by a later broader duplicate;
- duplicate `importance` remains the existing stored value unless explicitly changed through `/memory-admin edit`.

The add command reports the actual stored privacy class, reveal scope, and importance after the write.

### Member-wide purge and authored evidence

A member-wide purge removes:

1. every Memory Ledger record whose subject is that member, with normal cascading receipts/entities/contradictions/search data;
2. every receipt authored by that member on another subject's memory;
3. any other subject's memory that is left with zero receipts after those authored receipts are removed.

A cross-subject memory that still has another receipt survives. This preserves the Memory Ledger rule that every surviving memory has evidence while ensuring a member's authored receipt content is actually removed from the ledger.

`delete-member` and `delete-member-id` are intentionally scoped to the Memory Ledger. They do not silently delete Coven Registry or private identity/consent records; those stores have separate product semantics and must not be destroyed as a side effect of a Memory Ledger command.

## Data-access/correction/deletion handling

Member Memory Ledger requests are founder/admin mediated rather than exposed as a raw self-service database browser:

1. use `member-data` for a current member or `member-data-id` for an archived/departed member;
2. use `profile`, `show`, `search`, and `receipts` for private access review;
3. use `edit` for Memory Ledger corrections;
4. use `delete`, `delete-member`, or `delete-member-id` for permanent Memory Ledger deletion when appropriate.

The ID routes accept a positive decimal 64-bit Discord snowflake string so large Discord IDs are not forced through a lossy JSON-number boundary.

Any broader deletion request involving Registry or identity data must be handled explicitly by those feature boundaries rather than pretending a Memory Ledger purge erased data it did not touch.

## Audit behavior

Administrative mutations continue using the shared audit log. Audit events remain content-free: memory summaries, receipt excerpts, preferred names, and birth dates are not copied into generic operational audit payloads.

Member-wide deletion records only the member target and content-free counts for subject memories, cross-subject authored receipts, and evidence-less memories deleted as a consequence.

## Feature flag

The cog is controlled by:

```env
ENABLE_MEMORY_ADMIN=true
```

It defaults enabled because it is the private safety/control surface for the persistent Memory Ledger. Automatic extraction remains separately governed by the runtime memory policy and later implementation phases.

## Validation

Phase-3 tests cover:

- founder/admin home-guild authorization;
- ephemeral denial behavior;
- archived/departed member ID validation;
- content-free status/member summaries;
- restricted/admin-only counting;
- duplicate privacy tightening and no-loosening;
- cross-subject authored receipt inventory and purge;
- preservation of a memory that still has another receipt;
- deletion of a memory left with zero evidence;
- Registry survival after Memory Ledger-only deletion;
- content-free deletion audit metadata.

The repository quality gates remain:

```bash
ruff check .
pytest
```

## Rollback

Phase 3 adds no database schema migration. Rolling back the command surface means deploying the previous application revision or disabling `ENABLE_MEMORY_ADMIN`. Existing schema-v9 data and persistent Memory Ledger settings remain intact.
