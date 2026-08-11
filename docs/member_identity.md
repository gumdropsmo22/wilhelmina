# Member identity contract

Wilhelmina keeps two distinct names for every inducted adult member:

- the current Discord display name, refreshed when Discord changes it;
- the preferred name the member gives Wilhelmina during induction.

Neither name replaces the other. Approved memory-aware chat may use either name and may explicitly notice the difference between them.

## Birth date and age

Induction collects the member's full self-reported birth date in ISO `YYYY-MM-DD` format. The full date is the canonical source of truth. Age is never stored as a permanent number because it becomes stale; trusted local code recalculates it using the configured server date.

After authorization and current-consent checks, the trusted identity context for approved Wilhelmina server chat and direct conversations with Wilhelmina contains:

- current Discord display name;
- preferred name;
- full birth date;
- current calculated age.

This deliberately gives Wilhelmina enough context to use age, birthday timing, and the contrast between both names in her adult conversational persona. The full birth date is not reduced to age-only context because the product requires Wilhelmina herself to know the canonical birthday inside approved trusted context.

The same information must not be copied into general-purpose commands, operational logs, public Registry cards, error messages, or unrelated AI features. Local code decides whether the member/context is authorized before constructing the trusted identity object.

## Adult gate

A birth date that calculates to under eighteen blocks completion of the adult induction flow. Future dates and malformed dates are rejected. February 29 birthdays use February 28 as the anniversary in non-leap years for age calculation.

## Versioned memory disclosure

Adult-memory consent is versioned rather than treated as a permanent blank cheque.

The current disclosure covers the intended next-phase behavior:

- messages a member sends to Wilhelmina may be remembered;
- this includes direct messages with Wilhelmina;
- ordinary permitted social memories may later resurface in approved memory-aware conversation;
- that may include Wilhelmina bringing one participating adult member's ordinary social memory into a relevant conversation with another participating adult member.

A legacy identity profile is migrated with `legacy-adult-memory-v1`. That preserves the existing profile without pretending the older disclosure authorized the newer DM/cross-member behavior.

The current disclosure version is `2026-08-interaction-dm-cross-reveal-v2`. A member with only legacy consent must complete the current disclosure before trusted memory-aware identity context is available.

The existence of a profile and the validity of its current consent are deliberately separate concepts:

- `profile_is_complete(...)` means the private identity row exists;
- `profile_has_current_consent(...)` means that row has accepted the current disclosure.

This preserves compatibility for administrative/profile code while giving chat/memory code an explicit consent gate.

## OpenAI boundary

The model receives identity data only through an explicit allow-listed context assembled by trusted Python code. The model does not decide whose profile to load, whether a conversation is authorized, how age is calculated, or whether consent is current.

Private member-memory/chat calls use the shared asynchronous Responses API boundary with response storage forced off. Live private calls are designed to fail closed unless the deployment explicitly asserts an approved enhanced OpenAI retention posture (`mam` or `zdr`). Provider-side MAM/ZDR configuration remains an OpenAI-project setting; the runtime value is an assertion, not a substitute for actual approval/configuration.

Prompts, responses, preferred names, and birth dates must not enter operational logs. Safe telemetry may include request ID, model, token usage, latency/status, and content-free identifiers.

## Schema migration

The private member-identity schema uses version 8 for the versioned-consent migration.

Fresh profiles store `memory_consent_version` directly. Existing version-7-style profiles gain the column with the legacy consent value. This migration is intentionally non-destructive: names and birth dates remain intact while richer memory-aware behavior stays blocked until current consent is recorded.
