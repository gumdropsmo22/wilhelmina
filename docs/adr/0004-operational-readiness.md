# ADR 0004: Operational readiness inspection

Date: 2026-05-21

## Status

Accepted

## Context

Wilhelmina now has durable SQLite storage for guild configuration and audit events. Before onboarding or automation can be built safely, administrators need a deterministic way to inspect whether the dedicated home guild is configured correctly.

Phase 3 needs to answer practical questions:

```txt
Is HOME_GUILD_ID configured?
Does the command run in the home guild?
Does the guild_config row exist?
Do configured roles exist?
Do configured channels exist?
Can the bot view and send in those channels?
Can recent audit events be listed?
```

## Decision

Add a report-only readiness layer:

```txt
services/config_validation.py
/admin setup status
/admin setup checklist
/admin permissions
/admin logs recent
```

The validation service returns structured checks and issues. The admin commands format those results for ephemeral administrator responses.

## Boundaries

Phase 3 is inspection only.

It does not add:

```txt
role creation
channel creation
role assignment
automatic permission edits
onboarding state
scheduled jobs
memory
server takeover
server transformation
```

All Discord objects are inspected through the live guild object available to the command. No command added in this phase changes Discord server structure.

## Consequences

Positive:

- Administrators can see exactly what is missing before onboarding exists.
- The bot reports permission problems without attempting to fix them.
- Readiness logic is testable without live Discord API calls.
- Audit log visibility becomes available through `/admin logs recent`.

Tradeoffs:

- The bot still depends on humans to create roles/channels and set permissions.
- Permission inspection is best-effort when Discord objects or bot member data are unavailable.
- Setup automation remains intentionally out of scope until later phases.

## Test expectations

Phase 3 tests cover:

```txt
home guild validation
complete config validation
missing role reporting
missing channel reporting
missing channel permission reporting
warning-level optional permissions
missing config row reporting
bad timezone reporting
admin readiness helper formatting
audit event formatting
```
