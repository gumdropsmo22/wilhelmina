# ADR 0001: Dedicated Server Runtime

## Status

Accepted

## Context

Wilhelmina previously had possible roadmap paths involving existing-server transformation, channel archival, or server takeover workflows.

Those paths create avoidable risk: destructive channel changes, permission mistakes, irreversible archive moves, and coupling future onboarding work to an unstable migration process.

## Decision

Wilhelmina will target a brand-new dedicated Discord server.

The runtime only supports:

```env
SERVER_MODE=dedicated
```

Existing-server takeover, automatic archival, and server transformation modes are not supported. Configuration validation rejects unsupported server modes.

## Consequences

- Startup and command sync use `HOME_GUILD_ID` as the dedicated server identity.
- `DEV_GUILD_ID` remains a temporary compatibility alias for `HOME_GUILD_ID`.
- Future onboarding, roles, broadcasts, memory, and admin configuration should assume one home guild.
- Destructive channel migration logic is out of scope.
- Server setup should be explicit, admin-driven, and reversible.
