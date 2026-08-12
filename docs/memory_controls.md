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
- `/memory-admin member-data` — content-free counts used to service a member data request.

Admin search may intentionally include every reveal scope. This does not change the normal chat retrieval defaults and does not make `admin_only` records socially revealable.

## Manual mutation

The founder/admin surface supports:

- `/memory-admin add` — admin-authored memory with an honest `admin` receipt;
- `/memory-admin edit` — deterministic local correction of record fields;
- `/memory-admin delete` — permanent deletion of one record and dependent receipts/entities/contradiction/search rows;
- `/memory-admin delete-member` — permanent deletion of all Memory Ledger rows for one member.

Single-record deletion requires the exact confirmation text `DELETE`.

Member-wide Memory Ledger deletion requires the exact confirmation text `DELETE MEMBER`.

`delete-member` is intentionally scoped to the Memory Ledger. It does not silently delete Coven Registry or private identity/consent records; those stores have separate product semantics and must not be destroyed as a side effect of a Memory Ledger command.

## Data-access/correction/deletion handling

Member Memory Ledger requests are founder/admin mediated rather than exposed as a raw self-service database browser:

1. use `member-data` for content-free inventory;
2. use `profile`, `show`, and `receipts` for private access review;
3. use `edit` for Memory Ledger corrections;
4. use `delete` or `delete-member` for permanent Memory Ledger deletion when appropriate.

Any broader deletion request involving Registry or identity data must be handled explicitly by those feature boundaries rather than pretending `delete-member` erased data it did not touch.

## Audit behavior

Administrative mutations continue using the shared audit log. Audit events remain content-free: memory summaries, receipt excerpts, preferred names, and birth dates are not copied into generic operational audit payloads.

Member-wide deletion records only the member target and number of Memory Ledger records deleted.

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
- content-free status/member summaries;
- restricted/admin-only counting;
- member-wide deletion cascades;
- Registry survival after Memory Ledger-only deletion;
- content-free deletion audit metadata.

The repository quality gates remain:

```bash
ruff check .
pytest
```

## Rollback

Phase 3 adds no database schema migration. Rolling back the command surface means deploying the previous application revision or disabling `ENABLE_MEMORY_ADMIN`. Existing schema-v9 data and persistent Memory Ledger settings remain intact.
