# Welcome flow

## Status

BUILT on the Welcome feature branch. Automated validation is required before merge. Live Discord validation is intentionally deferred to the final whole-project testing phase.

## Product behavior

Welcome is an automatic join greeting, not a slash command and not a second onboarding ceremony.

When `ENABLE_WELCOME=true`, Wilhelmina listens for a human member joining `HOME_GUILD_ID`. If `guild_config.welcome_channel_id` is configured and resolves to a text channel, she posts one short greeting in that channel and mentions the joining member.

The greeting uses the shared `welcome` Persona Engine profile. AI generation is optional: if generation is unavailable or fails, Wilhelmina uses the deterministic fallback already defined by the Persona Engine:

> Step inside. The house has already noticed you.

The member mention is attached deterministically outside generated copy, so the model does not choose whom the greeting targets.

## Boundaries

This tranche does **not**:

- assign or remove roles;
- change channel permissions;
- start, approve, reject, or complete onboarding state;
- alter Covenant acceptance;
- DM the joining member;
- collect new profile fields;
- change the existing age rule;
- enable broad listening or memory collection;
- create a `/welcome` slash command;
- make a live OpenAI call in automated tests.

The Coven Registry continues to own its existing member-join registration behavior independently.

## Configuration

Runtime feature flag:

```env
ENABLE_WELCOME=false
```

Welcome is disabled by default until final rollout.

Server configuration:

```text
welcome_channel_id
```

Set the channel through the existing `/admin config set-channel` surface.

Because Discord member-join events require member events, enabling Welcome requests the Discord Members intent. The matching privileged intent must be enabled for the bot application before live rollout.

## Failure behavior

- Bot accounts are ignored.
- Joins outside `HOME_GUILD_ID` are ignored.
- Missing `welcome_channel_id` is a silent no-op with an operational log entry.
- A configured ID that is not a usable text channel is skipped and logged.
- Persona-generation failure uses deterministic fallback copy.
- Discord send failure is logged and does not mutate onboarding, registry, roles, or other state.

## Automated acceptance criteria

The test suite must prove:

- the feature flag defaults off and can be enabled independently;
- enabling Welcome requests the Members intent without requesting Message Content;
- a configured home-guild human join posts exactly one greeting;
- generated copy cannot choose the member mention target;
- provider/persona failure falls back deterministically;
- unconfigured Welcome is silent;
- bot users and wrong-guild joins are ignored.

## Final live validation

`LIVE VALIDATION PENDING`

The later whole-project Discord testing pass should verify the real Developer Portal Members intent, configured welcome channel, member mention behavior, visual copy quality, and coexistence with Coven Registry join handling. Live validation is deliberately not pulled forward into the current build phase.
