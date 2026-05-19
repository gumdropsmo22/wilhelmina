# ADR 0002: Unbundled Feature Cogs

## Status

Accepted

## Context

The previous `cogs.oracles` module grouped multiple unrelated slash commands under one umbrella feature flag: `/roll`, `/8ball`, and `/fortune`.

That made feature ownership blurry. It also meant enabling one command implied enabling the whole bundle, even when each command has different dependencies, behavior, testing needs, and future product paths.

## Decision

Remove the active `cogs.oracles` umbrella module and split the commands into standalone feature cogs:

```txt
cogs.roll
cogs.eight_ball
cogs.fortune
```

Each feature gets its own environment flag:

```env
ENABLE_ROLL=false
ENABLE_EIGHT_BALL=false
ENABLE_FORTUNE=false
```

Shared logic lives in service modules instead of a branded command bundle:

```txt
services.rolls
services.eight_ball
services.fortune
services.ai
```

## Compatibility

`ENABLE_ORACLES=true` is retained temporarily as a compatibility shim that enables the three split features. It does not load `cogs.oracles`, and new configuration should not use it.

## Consequences

- Each command can be tested, enabled, disabled, and evolved independently.
- AI concerns live in `services.ai`, not inside command cogs.
- Future features such as tarot, rituals, readings, onboarding, reminders, or chat should become their own cogs/services rather than joining a vague umbrella.
- User-facing command names remain stable while internal architecture becomes cleaner.
