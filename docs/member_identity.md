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

This deliberately gives Wilhelmina enough context to use age, birthday timing, and the contrast between both names in her conversational persona. The full birth date is not reduced to age-only context because the product requires Wilhelmina herself to know the canonical birthday inside approved trusted context.

The same information must not be copied into general-purpose commands, operational logs, public Registry cards, error messages, or unrelated AI features. Local code decides which member/profile and interaction are in scope before constructing the trusted identity object.

## Current under-18 behavior — PRODUCT DECISION PENDING

The existing runtime behavior remains unchanged in this tranche: a birth date that calculates to under eighteen blocks completion of the identity profile. Future dates and malformed dates are rejected. February 29 birthdays use February 28 as the anniversary in non-leap years for age calculation.

This behavior is intentionally preserved only to avoid changing an unresolved product decision while removing unrelated consent architecture.

## Identity profile and memory eligibility

A completed private identity profile—not a separately versioned memory permission—is the identity prerequisite for approved interaction-scoped memory behavior.

`profile_is_complete(...)` means the private identity row exists. `profile_is_memory_eligible(...)` currently delegates to that profile state. Memory extraction still separately enforces its real runtime boundaries, including:

- configured home guild;
- interaction collection mode;
- persistent Memory Ledger pause/resume state;
- approved direct-interaction source scope;
- provider/privacy runtime readiness;
- queue claim ownership and final mutation-time authorization.

Profile existence is not a substitute for those controls. It simply replaces the agent-created `adult_memory_consent` / exact `memory_consent_version` gate.

The old helper name `profile_has_current_consent(...)` remains temporarily as a compatibility alias for already-reviewed Phase-4 callers. It no longer checks a consent version and must not be treated as a permission API. The later cleanup/migration tranche should remove that compatibility name entirely.

## Legacy consent columns are non-authoritative

Schema v8 still physically contains:

- `adult_memory_consent_at`;
- `memory_consent_version`.

They remain only so this runtime correction does not destructively rebuild the identity table before the dedicated migration tranche. Existing values are preserved as historical compatibility data. New profiles receive a non-authoritative compatibility marker in the obsolete version column because the current table still requires a non-null value.

Neither field grants, revokes, upgrades, or downgrades memory/chat authorization.

The induction UI no longer asks a member to type `I CONSENT`, and identity completion no longer depends on a consent phrase or exact disclosure version.

## OpenAI boundary

The model receives identity data only through an explicit allow-listed context assembled by trusted Python code. The model does not decide whose profile to load, whether a conversation/source is authorized, or how age is calculated.

Private member-memory/chat calls use the shared asynchronous Responses API boundary with response storage forced off. Live private calls are designed to fail closed unless the deployment explicitly asserts an approved enhanced OpenAI retention posture (`mam` or `zdr`). Provider-side MAM/ZDR configuration remains an OpenAI-project setting; the runtime value is an assertion, not a substitute for actual approval/configuration.

Prompts, responses, preferred names, and birth dates must not enter operational logs. Safe telemetry may include request ID, model, token usage, latency/status, and content-free identifiers.

## Schema migration status

The private member-identity schema remains version 8 during this tranche. No columns are dropped here.

Existing version-7-style profiles still gain `memory_consent_version` so old databases remain readable, but that migrated value is no longer an authorization gate. Names and full birth dates remain intact.

The next dedicated migration tranche may rebuild the table and physically remove obsolete consent columns after this runtime/UI change has proven stable.
