# Wilhelmina Phase 2 Persistence Implementation Bundle

This bundle contains the intended Phase 2 implementation files for:

- SQLite persistence
- guild config service
- audit log service
- `/admin config ...` command wiring
- settings/database path updates
- tests
- README, `.env.example`, ADR 0003, and AGENTS.md updates

Repository write status from the GitHub connector:

- PR #25 was merged into `main`.
- Branch `roadmap/phase-2-persistence-guild-config` was created from the merged Phase 1 baseline.
- `services/database.py` was committed to that branch.
- Subsequent `create_file`/`update_file` writes were blocked by the connector safety gate, so the remaining implementation is supplied here as a file bundle.

Local isolated validation:

```txt
16 passed
```

The local validation covered:

- database initialization idempotence
- schema migration row creation
- guild config CRUD
- partial clear and full clear
- snowflake/timezone validation
- audit event insert/list/deserialization
- settings database path default and relative path resolution

Apply order:

```bash
cp -R services tests config cogs docs README.md .env.example AGENTS.md /path/to/repo/
ruff check .
pytest
```

Do not merge the GitHub branch until the remaining files in this bundle are committed and CI is green.
