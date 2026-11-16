# Owner decision and audit repairs — 2026-10-26

The founder explicitly rejected the unrequested minimum-age induction policy. This is a project for fun among five known adults. There is no product age gate or age-verification ceremony. Birthdays and local age calculation remain useful character context; malformed/future date validation remains. AGENTS section 7 records this decision for future agents.

## Repairs

- Member purges revoke queued/in-flight extraction claims and erase their source text in the purge transaction. Late provider results cannot recreate prior data; future interactions remain allowed.
- Unicode normalization preserves Arabic/mixed-language memory and search terms. Schema marker 13 rekeys existing records without deleting rows/receipts. The migration belongs to the caller transaction; a normalization collision aborts/rolls back rather than discarding evidence. Previously collapsed summaries cannot be magically reconstructed; examine retained receipts if repair is needed.
- Conversational FTS uses ranked OR matches so question/filler terms do not require every word to appear in a memory. Guild/reveal filters remain authoritative.
- Rules administration enforces Manage Server locally. Public rules acceptance remains public.
- Help hides all private administration roots; optional invalid relative embed icons are omitted.
- Bulk deletion tombstones both retained and in-flight Chat source turns.
- Memory validation reuses value-aware credential scanning instead of blocking harmless topic words. Actual secrets remain blocked.
- 8-Ball uses canonical persona instructions and bounds both generated answers and final embed descriptions.

## Upgrade and rollback

Stop the single bot process and take a consistent SQLite backup before upgrading. Test a representative restored copy first. Identity data needs no schema migration for removing the age gate. Unicode key migration is transactional; resolve reported collisions on the restored copy before production upgrade. Restore the pre-upgrade database together with the prior code for rollback; do not run old ASCII key writers against the migrated database. No new collection scope, permission ceremony, or runtime feature is introduced.

Automated validation uses mocked providers. LIVE VALIDATION PENDING; no production Discord/provider settings were changed. The historical audit and draft handoff predate this owner decision and must not revive the former age policy.
