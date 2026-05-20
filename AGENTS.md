# AGENTS.md

## Operating rules

- Build from updated `main` after PR #25.
- Keep Codex in review-only mode.
- Do not let Codex own architecture or broad implementation.
- Do not revive `cogs.oracles`, `utils.persona`, or an Oracle umbrella module.
- Keep the active pattern: one feature equals one cog and one service boundary when reusable logic exists.
- Add tests with every behavior change.
- Update README, `.env.example`, and ADR docs when architecture or runtime configuration changes.

## Phase 2 scope

Allowed:

```txt
SQLite persistence
guild_config storage
audit_log storage
admin config commands
database settings
tests
docs
```

Not allowed in Phase 2:

```txt
onboarding state machine
role assignment automation
scheduled jobs
memory
tarot/readings/ritual expansion
server takeover
channel archival
server transformation
automatic mass role/channel mutation
new Oracle umbrella
```

## Quality gates

Run before review:

```bash
ruff check .
pytest
```

A change is not done because code exists. It is done when the implementation, tests, docs, config examples, and rollback/migration notes are all aligned.
