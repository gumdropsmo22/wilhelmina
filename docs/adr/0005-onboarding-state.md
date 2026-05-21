# ADR 0005: Onboarding state foundation

Date: 2026-05-21

## Status

Accepted

## Context

Wilhelmina has dedicated-server runtime, persistent guild configuration, audit logging, and operational readiness inspection. The next safe step is to track onboarding state before any role automation, welcome flow, or rules acknowledgement workflow exists.

Administrators need to inspect and manually correct onboarding state without the bot mutating Discord roles or channels.

## Decision

Add a SQLite-backed `onboarding_state` table and a service boundary:

```txt
services/onboarding.py
```

Add admin-only commands under:

```txt
/admin onboarding view
/admin onboarding list
/admin onboarding start
/admin onboarding approve
/admin onboarding reject
/admin onboarding complete
/admin onboarding override
```

State values are:

```txt
pending
approved
rejected
completed
```

All state changes are auditable through the existing `audit_log` table.

## Boundaries

This phase records state only.

It does not add:

```txt
role assignment
role removal
channel creation
channel permission changes
welcome messages
rules acknowledgement UI
scheduled jobs
memory
server takeover
server transformation
```

## Consequences

Positive:

- Onboarding state is durable and inspectable.
- Admins can manually override mistakes.
- Future role automation has a deterministic state ledger to consume.
- Audit rows show who changed onboarding state and when.

Tradeoffs:

- The bot does not yet move users between pending/member roles.
- The bot does not yet greet users or collect rules acknowledgement.
- Human admins remain responsible for acting on the state until later phases.

## Migration notes

Schema version advances to 2 and adds:

```sql
CREATE TABLE IF NOT EXISTS onboarding_state (...)
```

Existing SQLite databases are initialized idempotently. Deployment should still back up `DATABASE_PATH` before upgrading.
