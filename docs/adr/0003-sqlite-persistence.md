# ADR 0003: SQLite persistence for guild config and audit log

Date: 2026-05-20

## Status

Accepted

## Context

Wilhelmina now runs as a dedicated-server bot. The runtime needs durable storage for its own home guild configuration before onboarding, scheduling, memory, or larger feature systems can be built safely.

The immediate data requirements are small and local:

```txt
guild_config
audit_log
schema_migrations
```

The bot does not need distributed writes, cross-server tenancy, analytics queries, or external database infrastructure in this phase.

## Decision

Use SQLite through Python's standard `sqlite3` module for Phase 2 persistence.

Add:

```txt
services/database.py
services/guild_config.py
services/audit_log.py
```

Store the database at:

```env
DATABASE_PATH=data/wilhelmina.sqlite3
```

Relative database paths resolve from the repository root through runtime settings.

The schema version is tracked in `schema_migrations` so later migrations can be explicit instead of improvised.

## Schema

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id INTEGER PRIMARY KEY,
    admin_role_id INTEGER,
    member_role_id INTEGER,
    pending_role_id INTEGER,
    welcome_channel_id INTEGER,
    onboarding_channel_id INTEGER,
    broadcast_channel_id INTEGER,
    admin_log_channel_id INTEGER,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    actor_user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);
```

## Boundaries

This decision adds persistence only.

It does not add:

```txt
onboarding state machines
role assignment automation
scheduled jobs
memory
server takeover
channel archival
server transformation
tarot/readings/ritual expansion
```

The admin config commands store and validate IDs. They do not mutate Discord server structure.

## Consequences

Positive:

- Simple local development and deployment.
- No new external service dependency.
- Easy backup: copy the SQLite file.
- Deterministic tests with temporary database files.
- Clean path to later migrations.

Tradeoffs:

- SQLite is single-file local state.
- Multi-instance bot deployments would need a later database decision.
- PostgreSQL or another external database requires a new ADR and migration plan.

## Rollback and migration notes

To rollback Phase 2 persistence in development:

```txt
1. Stop the bot.
2. Back up or delete the SQLite file at DATABASE_PATH.
3. Revert the persistence PR.
```

For future schema versions:

```txt
1. Add an explicit migration.
2. Insert the new version into schema_migrations.
3. Document backup and rollback steps in the PR.
```
