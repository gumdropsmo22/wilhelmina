# ADR 0005: Onboarding state foundation

Date: 2026-05-21

## Status

Accepted

## Context

Wilhelmina has dedicated-server runtime, persistent guild configuration, audit logging, and operational readiness inspection. The next safe step is to track onboarding state before any role automation, welcome flow, or rules acknowledgement workflow exists.

Administrators need to inspect, summarize, audit, and manually correct onboarding state without the bot changing Discord roles or channels.

## Decision

Add a SQLite-backed `onboarding_state` table and a service boundary:

```txt
services/onboarding.py
```

The service owns deterministic onboarding state transitions and read models:

```txt
start_onboarding
approve_onboarding
reject_onboarding
complete_onboarding
override_state
update_notes
get_onboarding_record
list_onboarding_records
summarize_onboarding
list_onboarding_history
```

Add admin-only commands under:

```txt
/admin onboarding summary
/admin onboarding view
/admin onboarding history
/admin onboarding list
/admin onboarding start
/admin onboarding approve
/admin onboarding reject
/admin onboarding complete
/admin onboarding notes
/admin onboarding override
```

State values are:

```txt
pending
approved
rejected
completed
```

All state changes and note updates are auditable through the existing `audit_log` table. Per-user onboarding history is read from audit events targeting that user's ID.

## Boundaries

This phase records and reports state only.

It does not add role assignment, role removal, channel creation, permission edits, welcome messages, rules acknowledgement UI, scheduled jobs, memory, or server transformation workflows.

## Consequences

Positive:

- Onboarding state is durable and inspectable.
- Admins can summarize onboarding load by state.
- Admins can view a user's onboarding history.
- Admins can update or clear notes without changing state.
- Admins can manually override mistakes.
- Future role automation has a deterministic state ledger to consume.
- Audit rows show who changed onboarding state and when.

Tradeoffs:

- The bot does not yet move users between pending/member roles.
- The bot does not yet greet users or collect rules acknowledgement.
- Human admins remain responsible for acting on the state until later phases.

## Migration notes

Schema version advances to 2 and adds `onboarding_state`.

No additional schema change is required for summary, notes update, or history. Summary reads from `onboarding_state`; history reads from `audit_log` by target user ID.

Existing SQLite databases are initialized idempotently. Deployment should still back up `DATABASE_PATH` before upgrading.
