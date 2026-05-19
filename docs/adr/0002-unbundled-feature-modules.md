# ADR 0002: Unbundled Feature Modules

## Status

Accepted

## Context

Wilhelmina previously grouped `/roll`, `/8ball`, and `/fortune` under an `oracles` cog and `ENABLE_ORACLES` feature flag.

That umbrella made unrelated capabilities harder to reason about. A dice roller, a yes/no answer command, and a fortune generator have different runtime needs, testing surfaces, and future persistence requirements.

## Decision

Wilhelmina will use one cog per user-facing capability or tightly related capability set.

The old umbrella cog is removed from the active runtime:

```txt
cogs.oracles
```

The replacement modules are:

```txt
cogs.roll
cogs.eight_ball
cogs.fortune
```

Each optional feature has its own flag:

```env
ENABLE_ROLL=false
ENABLE_EIGHT_BALL=false
ENABLE_FORTUNE=false
```

`ENABLE_ORACLES` may remain temporarily as a compatibility shim for old `.env` files, but it is not a supported configuration path for new setups.

## Consequences

- Features can be enabled, disabled, tested, and deployed independently.
- Shared AI access belongs in `services.ai`, not in command cogs.
- Feature-specific generation belongs in small services such as `services.eight_ball` and `services.fortune`.
- Commands keep their existing names so users do not need to relearn slash commands.
- Future features should not be added to broad thematic buckets unless they share runtime state and behavior.
