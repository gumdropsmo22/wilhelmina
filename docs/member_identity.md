# Member identity contract

Wilhelmina keeps two distinct names for every inducted member:

- the current Discord display name, refreshed when Discord changes it;
- the preferred name the member gives Wilhelmina during induction.

Neither name replaces the other. Approved memory-aware chat may use either name and may explicitly notice the difference between them.

## Birth date and age

Induction collects the member's full self-reported birth date in ISO `YYYY-MM-DD` format. The full date is the canonical source of truth. Age is never stored as a permanent number because it becomes stale; trusted local code recalculates it using the configured server date.

For an already-authorized Wilhelmina interaction, the trusted identity context contains:

- current Discord display name;
- preferred name;
- full birth date;
- current calculated age.

This deliberately gives Wilhelmina enough context to use age, birthday timing, and the contrast between both names in her conversational persona. The full birth date is not reduced to age-only context because Wilhelmina herself needs the canonical birthday inside approved trusted context.

The same information must not be copied into general-purpose commands, operational logs, public Registry cards, error messages, or unrelated AI features. Local code decides which member/profile and interaction are in scope before constructing the trusted identity object.

## Current under-18 behavior — PRODUCT DECISION PENDING

The existing runtime behavior remains unchanged: a birth date that calculates to under eighteen blocks completion of the identity profile. Future dates and malformed dates are rejected. February 29 birthdays use February 28 as the anniversary in non-leap years for age calculation.

This is preserved only because the age rule is a separate unresolved product decision. The consent cleanup does not expand, remove, or reinterpret it.

## Identity profile and memory eligibility

A completed private identity profile is the identity prerequisite for approved interaction-scoped memory behavior.

`profile_is_complete(...)` means the private identity row exists. `profile_is_memory_eligible(...)` currently delegates to that profile state. Memory extraction separately enforces its actual runtime boundaries, including:

- configured home guild;
- interaction collection mode;
- persistent Memory Ledger pause/resume state;
- approved direct-interaction source scope;
- provider/privacy runtime readiness;
- queue claim ownership and final mutation-time authorization.

Profile existence is not a substitute for those controls. There is no separate adult-memory-consent permission, consent phrase, or exact disclosure-version gate.

## Schema v12

The private identity table now stores only canonical identity data and timestamps:

- guild ID;
- Discord user ID;
- preferred name;
- full birth date;
- created timestamp;
- updated timestamp.

Current Discord display name remains authoritative in the Coven Registry and is joined into the trusted identity object when loaded.

Schema v12 physically removes the obsolete `adult_memory_consent_at` and `memory_consent_version` columns. The old compatibility constants, save arguments, consent property, and `profile_has_current_consent(...)` alias are also removed.

### v7/v8 migration

Legacy identity tables are rebuilt transactionally:

1. verify the canonical identity columns needed for preservation;
2. rename the legacy table inside the current SQLite transaction;
3. create the v12 table;
4. copy guild/user IDs, preferred name, full birth date, and original created/updated timestamps;
5. drop the renamed legacy table;
6. record schema version 12.

If the copy violates the v12 table contract, the transaction rolls back. Tests cover both v7 and v8 source shapes plus a forced-copy failure to prove the legacy table/data are restored intact rather than left half-migrated.

## OpenAI boundary

The model receives identity data only through an explicit allow-listed context assembled by trusted Python code. The model does not decide whose profile to load, whether a conversation/source is authorized, or how age is calculated.

Private member-memory/chat calls use the shared asynchronous Responses API boundary with response storage forced off. Live private calls fail closed unless the deployment explicitly asserts an approved enhanced OpenAI retention posture (`mam` or `zdr`). Provider-side MAM/ZDR configuration remains an OpenAI-project setting; the runtime value is an assertion, not a substitute for actual approval/configuration.

Prompts, responses, preferred names, and birth dates must not enter operational logs. Safe telemetry may include request ID, model, token usage, latency/status, and content-free identifiers.
