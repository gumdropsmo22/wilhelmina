# AGENTS.md

## Operating rules

- Build from the latest target branch before starting a new tranche.
- Keep architecture decisions explicit in project documentation and pull-request scope.
- Do not revive `cogs.oracles`, `utils.persona`, or an Oracle umbrella module.
- Keep the active pattern: one feature equals one cog and one reusable service boundary when shared logic exists.
- Add or update tests with every behavior change.
- Update README, `.env.example`, and ADR or feature documentation whenever architecture or runtime configuration changes.
- Do not commit secrets, tokens, database files, or live Discord identifiers.

## Current authorized scope

Allowed:

```txt
SQLite persistence
guild_config and audit_log storage
Covenant Gate and Coven Registry
scheduled broadcasts
Memory Ledger persistence and admin controls
OpenAI integration behind explicit feature flags
automatic Memory Ledger collection after its extractor and Discord event layer are reviewed
open-chat integration after the one-channel reveal boundary is enforced
tests and documentation
```

Not allowed without a separate approved tranche:

```txt
server takeover
channel archival
server transformation
automatic mass role/channel mutation
new Oracle umbrella
tarot/readings/ritual expansion outside their own approved feature work
unreviewed public exposure of private Memory Ledger records
committing or logging API keys, Discord tokens, or prohibited private data
```

## Memory Ledger rules

- The founder/admin controls collection globally; there is no member-level memory opt-out in the approved design.
- A legacy `memory_opt_out` database column may remain temporarily for compatibility, but it is inert and must not affect collection.
- Prohibited information must be rejected or redacted before any external AI request.
- Ordinary replacement permanently deletes the superseded memory and receipts.
- Conflicting gossip remains separate, attributed, and linked through cascading contradiction records.
- Admin-authored memories use an admin receipt rather than fabricated Discord message metadata.

## Quality gates

Run before review:

```bash
ruff check .
pytest
```

A change is complete only when implementation, tests, docs, configuration examples, migration behavior, and rollback notes agree.
