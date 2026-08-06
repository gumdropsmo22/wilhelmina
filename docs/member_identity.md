# Member identity contract

Wilhelmina keeps two distinct names for every inducted adult member:

- the current Discord display name, refreshed when Discord changes it;
- the preferred name the member gives Wilhelmina during induction.

Neither name replaces the other. Approved memory-aware chat may use either name and may explicitly notice the difference between them.

## Birth date and age

Induction collects the member's full self-reported birth date in ISO `YYYY-MM-DD` format. The full date is the canonical source of truth. Age is never stored as a permanent number because it becomes stale; trusted local code recalculates it using the configured server date.

The trusted identity context for the designated Wilhelmina channel and direct conversations in which she participates contains:

- current Discord display name;
- preferred name;
- full birth date;
- current calculated age.

This deliberately gives Wilhelmina enough context to use age, birthday timing, and the contrast between both names in her adult conversational persona.

The same information must not be copied into general-purpose commands, operational logs, public Registry cards, error messages, or unrelated AI features. Local code decides whether the current channel or DM is approved before constructing the trusted identity context.

## Adult gate

A birth date that calculates to under eighteen blocks completion of the adult induction flow. Future dates and malformed dates are rejected. February 29 birthdays use February 28 as the anniversary in non-leap years for age calculation.

## OpenAI boundary

The model receives identity data only through an explicit allow-listed context assembled by trusted Python code. The model does not decide whose profile to load, whether the channel is authorised, or how age is calculated. OpenAI requests remain asynchronous, response storage remains disabled, and prompts or identity values must not enter operational logs.
