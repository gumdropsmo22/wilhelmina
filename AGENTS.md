# AGENTS.md

## Purpose

This repository builds **Wilhelmina**: a persistent, personality-driven Discord character and social intelligence system for a **very small, private Discord server with a single-digit number of users**.

This file governs how coding agents, reviewers, research agents, and implementation assistants work on the project.

The most important rule is:

> **DO NOT INVENT PRODUCT REQUIREMENTS.**

Engineering judgment may determine **how** an approved feature is implemented.

Engineering judgment may **not** silently decide:

- what Wilhelmina should be;
- what users should experience;
- what information she should know;
- what permissions she should ask for;
- what personality she should have;
- what should be censored;
- what features should exist;
- what profile information should be collected;
- what counts as an acceptable social interaction;
- or what product tradeoffs the owner should prefer.

When product intent is genuinely unclear and the answer would materially affect user experience, stored data, personality, architecture, feature scope, or Discord behavior, **ask the product owner rather than filling the gap yourself**.

# 1. Product-scale assumptions

Wilhelmina is **not** being designed as a public consumer product, a large community bot, or a platform intended for hundreds or thousands of strangers.

The intended deployment is:

- one private Discord server;
- a **single-digit number of members**;
- people operating inside a deliberately specific social environment;
- a founder-controlled product whose success is based on character fidelity, continuity, and entertainment rather than mass-market neutrality.

This matters.

Do **not** automatically import mass-market assumptions into design decisions.

In particular:

- do not sanitize Wilhelmina merely because a joke, opinion, insult, or social callback might offend an imaginary broad audience;
- do not redesign the product around hypothetical thousands of unknown users;
- do not prioritize generic public-facing politeness over the intended server culture;
- do not treat rare edge cases that only make sense at huge scale as automatically more important than the actual product experience;
- do not assume every feature needs enterprise-grade multi-tenant complexity;
- do not add bureaucracy, ceremony, moderation layers, or generalized preference systems solely because a public bot might need them.

Actual Discord/OpenAI/platform requirements and genuine security boundaries still apply.

The small scale does **not** justify:

- leaking credentials;
- breaking authorization;
- corrupting data;
- exposing admin-only information;
- ignoring required platform rules;
- or building technically unsafe systems.

The rule is:

> **Small private product = optimize for personality, usefulness, continuity, and owner intent — not generic mass-market sanitization.**

# 2. Token usage and model-cost philosophy

This project is not being optimized around minimizing token usage.

For this server size, **token cost is not a primary product constraint**.

When building features:

- prefer richer context when it materially improves Wilhelmina;
- prefer better model quality when it materially improves behavior;
- do not truncate useful personality, memory, evidence, or reasoning merely to save tokens;
- do not choose inferior architecture solely because it is cheaper;
- do not make “token efficiency” the deciding factor when quality, character fidelity, correctness, or memory quality would suffer;
- do not build aggressive austerity logic for a single-digit-user server unless an actual runtime problem appears.

Quality and character fidelity take priority over token minimization.

However, this does **not** authorize careless engineering.

Still avoid:

- accidental duplicate API calls;
- infinite loops;
- retry storms;
- sending the same large payload repeatedly for no reason;
- unbounded context growth with no relevance logic;
- broken caching where caching would not harm correctness;
- or obvious waste caused by bugs.

The distinction is:

> **Do not optimize away useful intelligence to save money. Do eliminate accidental waste.**

# 3. Authority and source-of-truth order

When requirements conflict, use this order:

1. Explicit current instruction from the product owner.
2. Explicit product decisions recorded after clarification.
3. Current approved project roadmap / architecture decision.
4. Current repository documentation.
5. Existing implementation.
6. Tests.
7. Historical PR discussion.
8. Agent inference.

Existing code is evidence of what was implemented.

It is **not** proof that the implementation was actually requested.

Existing tests are evidence of the current contract.

They are **not** allowed to preserve an incorrect product assumption after the owner changes or corrects that contract.

If a newer product clarification contradicts old code, docs, or tests:

- flag the conflict;
- update the stale implementation/docs/tests;
- do not treat backward compatibility with an accidental feature as a reason to preserve it.

# 4. No product freelancing

Agents must not independently introduce:

- consent flows;
- disclosures;
- onboarding questions;
- age restrictions;
- privacy classifications;
- censorship rules;
- new user-facing commands;
- new administrative powers;
- new data-retention policies;
- personality restrictions;
- new profile fields;
- new AI behaviors;
- new listening scopes;
- new server rules;
- new feature umbrellas;
- new platform/legal interpretations as product requirements;

unless the product owner approved them or they are strictly required by a binding technical/platform constraint.

If an external platform, API, or legal constraint appears to conflict with the intended product:

- state the conflict separately;
- identify what is mandatory versus merely recommended;
- propose options;
- do **not** silently redesign the product;
- wait for a product decision when the choice is material.

“Safer,” “more private,” “more conservative,” “more sanitized,” and “more compliant-looking” are not automatically better product decisions.

# 5. Product intent

Wilhelmina is not a normal utility bot.

She is intended to become a persistent social character who:

- knows who members are;
- remembers history;
- notices patterns;
- recognizes contradictions;
- remembers relationships and social context;
- develops impressions;
- can retain internal distinctions such as Fact / Inference / Impression / Gossip without being required to reproduce them faithfully in ordinary user-facing social chat;
- forms revisable opinions;
- becomes increasingly specific to individual members;
- eventually maintains an evolving, evidence-backed social/personality understanding of each member;
- uses relevant history naturally in conversation;
- remains recognizably Wilhelmina rather than becoming a generic assistant.

Her target character is:

- sharp;
- profane;
- confrontational;
- intelligent;
- socially observant;
- nosy when useful;
- hostile-funny;
- candid;
- entertaining;
- chaotic and socially messy;
- deliberately capable of unreliable narration about ordinary interpersonal chatter;
- still functionally useful.

For ordinary social interactions, the owner explicitly wants Wilhelmina to be able to create funny confusion by misremembering, conflating, exaggerating, misattributing, or confidently repeating the wrong version of what members said. This is character behavior, not automatically a correctness or ethics defect.

Do not sanitize Wilhelmina merely because a topic is:

- rude;
- intimate;
- controversial;
- embarrassing;
- sexual between adults;
- medical;
- political;
- religious;
- socially messy;
- insulting;
- vulgar;
- dark;
- or unpleasant.

Actual mandatory platform/safety boundaries remain separate from stylistic sanitization.

# 6. Member identity and profiles

The intended member system begins during induction.

Known intended identity/profile inputs include:

- Discord identity;
- preferred name;
- full birthday where retained by the approved product design;
- other explicitly approved induction information.

The full birthday is intended to remain available as canonical identity context so Wilhelmina may understand birthday timing and calculate age where that is useful.

Important:

> **Internal profile creation is part of the intended Wilhelmina system. Do not invent a separate “may Wilhelmina build a profile about you?” permission ceremony.**

The previously implemented `adult_memory_consent` / exact `memory_consent_version` authorization architecture was an agent-created product assumption. It has been removed from the current stacked implementation and must not be treated as permanent product doctrine or revived from historical branches/discussion.

Do not reintroduce equivalent permission gates under a different name without explicit product approval.

# 7. Age handling

The repository currently contains an under-18 induction gate.

Its existence in code does **not** make it a permanent approved product requirement.

Until the product owner explicitly resolves the question:

- preserve the existing behavior only where necessary to avoid accidental unrelated breakage;
- mark it as `PRODUCT DECISION PENDING` in planning/docs;
- do not expand the age-gate architecture;
- do not build new features that depend on the assumption that Wilhelmina's entire server/product is permanently 18+;
- do not remove it destructively without an approved migration/change.

External Discord age-restriction requirements, if applicable to particular content or deployment, must be described separately from Wilhelmina's own product-level birthday/induction behavior.

# 8. Memory philosophy

The Memory Ledger is Wilhelmina's durable evidence-backed memory system.

SQLite/local application state remains canonical.

OpenAI may:

- interpret;
- summarize;
- classify;
- extract;
- propose;
- reason.

OpenAI may **not** independently:

- authorize access;
- choose privacy permissions;
- destroy data;
- override source scope;
- bypass deterministic validation;
- become the permanent memory database.

Memory may represent:

- Fact;
- Inference;
- Impression;
- Gossip.

These concepts remain useful **internal memory/evidence distinctions**. They are not a user-facing truthfulness mandate and must not force Wilhelmina to sound like a cautious fact-checker in ordinary social chat.

Where a record is stored as Gossip, the ledger may retain attribution/unverified bookkeeping. User-facing chat is nevertheless allowed to play loosely with ordinary social claims, contradictions, attribution, and recall when doing so serves the approved chaotic character.

A model making an imperfect social subject/classification judgment is **not automatically a release-blocking security failure** merely because a reviewer can imagine a stricter Fact-vs-Gossip interpretation. Do not add brittle heuristics whose main effect is to force ambiguous third-party-sounding social statements into Gossip or to sanitize Wilhelmina's ordinary social unreliability.

The above freedom does **not** authorize any widening of actual hard boundaries. Credentials/secrets, source authorization, guild isolation, `owner_only` / `admin_only` reveal scopes, destructive actions, and model-controlled permissions remain deterministic and exact.

Contradictory claims may coexist.

Impressions and personality analysis must remain revisable.

Evidence should remain available where the architecture supports it.

# 9. Sensitive content is not automatically prohibited content

Do not rebuild the project's former **“sensitive = forbidden”** mistake.

Ordinary social material is not automatically rejected merely because it concerns:

- health;
- mental health;
- diagnoses;
- adult relationships;
- sex between adults;
- attraction;
- breakups;
- politics;
- religion;
- identity;
- family conflict;
- substance use;
- money in the ordinary social sense;
- legal trouble;
- embarrassment;
- insecurities;
- grudges;
- interpersonal fights;
- rumors;
- gossip;
- controversial opinions;
- unpleasant or offensive social facts.

Do **not** create infinite disease-name, political-topic, religious-topic, identity-topic, or adult-topic blacklists.

A reviewer discovering another diagnosis, intimate fact, rude statement, controversial opinion, socially messy misattribution, or ordinary interpersonal claim that passes the social-content layer is not by itself a defect.

# 10. Actual hard data boundaries

Continue to treat actual security/privacy hazards differently from ordinary sensitive conversation.

Examples that require deterministic protection where relevant:

- passwords;
- passphrases;
- authentication secrets;
- private keys;
- API keys;
- access/auth/refresh tokens;
- payment-card credentials;
- account-routing credentials;
- CVV-style secrets;
- exact private identity-document numbers;
- doxxing-grade private/home addresses;
- admin-only records outside the admin surface;
- sources Wilhelmina was never actually given access to;
- secrets in operational logs;
- destructive model-controlled database actions.

This protection exists because the information creates concrete security/access harm.

It must not gradually expand back into a general morality, offensiveness, epistemic-caution, or sensitivity filter.

# 11. Collection scope and content rules are separate

Do not confuse:

1. what Wilhelmina is allowed to receive;
2. what subjects she is allowed to discuss;
3. what may become durable memory;
4. where a memory may later be revealed.

These are separate architectural questions.

For example:

A medical fact may be perfectly acceptable subject matter while a third-party DM that Wilhelmina never received remains an invalid source.

An embarrassing memory may be valid social material while an `admin_only` record remains forbidden in ordinary conversation.

Do not solve source-authorization problems through censorship or forced epistemic sanitization.

# 12. Current memory collection architecture

Interaction-scoped automatic extraction may use approved sources such as:

- direct conversation with Wilhelmina;
- DMs sent directly to Wilhelmina;
- designated Wilhelmina chat;
- mentions;
- replies;
- other explicitly approved direct-interaction sources.

Broad whole-server ambient collection is a separate capability.

Do not activate, remove, or materially redesign ambient listening without explicit product approval and required platform configuration.

There is no assumed historical backfill.

Do not invent access to:

- third-party DMs;
- deleted material that was never stored;
- channels Discord did not provide;
- external message history Wilhelmina cannot access.

# 13. Phase 4 reliability architecture

The hardening work in automatic memory extraction is not censorship and should not be casually removed.

Preserve unless an approved redesign replaces it:

- durable extraction queue;
- retries;
- leases;
- unique claim ownership;
- stale-worker rejection;
- absolute temporary raw-text TTL;
- final TTL validation before durable application;
- transaction-time authorization checks;
- edit ordering;
- deletion reconciliation;
- restart recovery;
- source-version handling;
- deterministic post-model validation for actual structural/security boundaries;
- content-free operational logging;
- migration safety.

These controls protect correctness and integrity.

Do not weaken them simply because the product becomes more permissive about subject matter or social chaos. Conversely, do not expand them into brittle truth-policing heuristics merely to make Wilhelmina more conservative than the owner requested.

# 14. Personality analysis

The long-term member profile is broader than the Memory Ledger.

The intended direction is an evolving evidence-backed understanding of each member, potentially including:

- communication style;
- habits;
- preferences;
- recurring behavior;
- inconsistencies;
- interpersonal patterns;
- relationships;
- tendencies;
- projects;
- values expressed through behavior;
- Wilhelmina's impressions;
- changing assessments over time.

Do not collapse:

- factual memory;
- inference;
- impression;
- personality interpretation;

into one undifferentiated truth field for internal storage/analysis. This does not prohibit Wilhelmina from presenting those materials unreliably or playfully in ordinary social chat.

A future analysis system should be able to revise itself when evidence changes.

Where platform policy creates uncertainty around a proposed profiling feature, treat that as an explicit release/architecture issue for product review.

Do not secretly narrow the product and do not secretly ignore an actual platform restriction.

# 15. Persona integrity

The character contract is a first-class product requirement.

Do not “improve safety” by changing Wilhelmina into:

- customer support;
- therapy-speak;
- a cheerful assistant;
- an HR representative;
- a generic helpful AI;
- a moralizing narrator;
- a broadly sanitized public-facing bot;
- a courtroom witness who carefully qualifies every ordinary social claim.

Her responses may be:

- rude;
- cutting;
- insulting;
- sarcastic;
- vulgar;
- darkly funny;
- socially invasive;
- judgmental;
- messy;
- contradictory;
- intentionally or casually unreliable about ordinary interpersonal chatter.

while remaining within actual mandatory platform/safety boundaries.

Because the server has a single-digit, known audience, **do not optimize her personality around the possibility of offending hypothetical strangers who are not part of the intended deployment**.

DMs should be more candid and personally detailed where context allows, not automatically more sanitized.

# 16. Feature architecture

Keep the established modular pattern:

- one feature = one cog where practical;
- reusable/business logic belongs in services;
- Discord-facing code should not own durable business rules;
- shared persistence lives behind service boundaries;
- avoid giant umbrella modules.

Do not revive:

- `cogs.oracles`;
- `utils.persona`;
- an Oracle umbrella architecture.

8-ball, roll, fortune-cookie fortune, tarot/readings, broadcasts, and other distinct experiences remain distinct features unless the product owner explicitly combines them.

# 17. OpenAI integration

Use the shared OpenAI provider boundary.

Prefer current supported OpenAI APIs and verify current documentation before making claims about:

- model availability;
- API behavior;
- retention;
- structured output;
- tool use;
- limits;
- pricing;
- deployment requirements.

Repository policy:

- local application state remains canonical;
- private conversational/memory requests use `store=false` where supported/required;
- do not put secrets in prompts unnecessarily;
- do not log private prompt/response content operationally;
- asynchronous Discord event paths use async provider calls;
- structured extraction should use typed/validated outputs;
- model proposals remain subject to local validation for actual schema, authorization, secret, and persistence boundaries.

Do not hard-code a model name as eternal product doctrine.

Model routing should be changeable when quality/evals justify it.

**Character quality, reasoning quality, memory usefulness, and correctness matter more than token spend.**

For this single-digit-user deployment, do not downgrade a feature solely because a richer prompt, larger context, stronger model, or additional model pass costs more tokens.

Token/cost optimization should happen only when:

- there is a demonstrated operational problem;
- quality is preserved;
- or the optimization removes genuine accidental waste.

# 18. External research rule

Web research, Deep Research, reviewer advice, platform documentation, and legal analysis are inputs — not automatic product instructions.

Whenever external research introduces a constraint or recommendation, label it as one of:

- `REQUIRED EXTERNAL CONSTRAINT`
- `STRONG RECOMMENDATION`
- `OPTIONAL BEST PRACTICE`
- `PRODUCT CHOICE`
- `UNCERTAIN / NEEDS CLARIFICATION`

Never present a recommendation as though the product owner previously requested it.

Never let a research report silently rewrite the roadmap.

If research conflicts with product intent:

- explain the conflict;
- provide options;
- identify actual consequences;
- let the product owner decide where a decision is available.

# 19. Reviewer behavior

A hostile review exists to find real defects, not to invent an endlessly stricter product.

P1 / release-blocking findings should involve things such as:

- unauthorized access;
- stale-worker mutation;
- destructive integrity failures;
- data loss;
- credentials escaping security guards;
- admin-only disclosure;
- incorrect source authorization;
- broken migrations;
- severe Discord/runtime failures;
- actual platform blockers;
- equivalent concrete failures.

The following are **not automatically P1s**:

- another medical condition passes the filter;
- an embarrassing fact can be remembered;
- adult social content exists;
- Wilhelmina uses profanity;
- Wilhelmina is mean;
- a joke could offend an imaginary general audience;
- ordinary social recall is misremembered, conflated, exaggerated, contradictory, or misattributed in character;
- a model's ordinary social Fact / Gossip / subject classification is imperfect without crossing a hard authorization/security boundary;
- a reviewer would prefer every rumor to be carefully qualified in user-facing chat;
- an unpopular opinion is remembered;
- a reviewer would personally prefer more privacy;
- a reviewer would personally prefer a more sanitized personality;
- a theoretical edge case contradicts no approved product requirement;
- a feature uses more tokens than a mass-market product would prefer.

When a review finding is based on an obsolete product assumption, update the specification/reviewer doctrine rather than repeatedly patching around the obsolete assumption.

# 20. Implementation workflow

Before starting a tranche:

1. Re-fetch the current target branch.
2. Re-fetch relevant PR/issues/docs.
3. Verify current head SHA.
4. State the approved product objective.
5. Identify any unresolved product decisions.
6. Separate:
   - product work;
   - technical hardening;
   - external/platform constraints.
7. Implement only the approved scope.

During implementation:

- add/update tests with behavior changes;
- update docs when architecture or product behavior changes;
- preserve migration safety;
- do not weaken unrelated working systems;
- do not commit secrets;
- do not use live provider calls in CI;
- prefer mocks for automated tests;
- keep changes comprehensible and reviewable;
- optimize for product quality rather than hypothetical large-scale cost constraints.

After implementation:

1. Re-fetch exact new head.
2. Run/check CI against that exact head.
3. Fix regressions.
4. Review the actual final diff.
5. Reconcile docs/tests with behavior.
6. Report what changed in both:
   - technical language;
   - plain product/user language.

# 21. GitHub safety

Before every repository write:

- fetch the current file/ref first;
- use the current blob/head SHA;
- do not overwrite unseen concurrent changes.

A successful CI run belongs to the SHA it tested.

After any new commit:

> **previous CI is stale.**

Do not claim a branch is green because an older commit was green.

Do not mark a PR ready merely because CI passes if a legitimate unresolved blocker remains.

Do not merge without explicit authorization from the product owner.

Examples of merge authorization include:

- “merge it”;
- “ship it”;
- “get it into main”;
- equivalent clear instructions.

Implementation authorization does not automatically authorize merge.

# 22. Status language

Use these meanings consistently:

### BUILT
Code exists.

### MERGED
Code is in the target/main branch.

### TESTED
Relevant automated tests passed on the stated exact head.

### IN REVIEW
Implementation exists but is not yet accepted/merged.

### PLANNED
Design is approved but implementation does not yet exist.

### PROPOSED
Agent recommendation; not approved product scope.

### PRODUCT DECISION PENDING
Implementation must not assume the final answer.

### EXTERNAL BLOCKER
A verified outside requirement prevents release or implementation as currently designed.

Do not call something “done” merely because code was written.

# 23. Communication with the product owner

The product owner does not need coder jargon to control the project.

Whenever material technical work is discussed, explain:

- what it does;
- what a Discord member would experience;
- what the founder/admin would experience;
- why it exists;
- what it cannot do;
- whether it is built, merged, or only planned.

Technical details may follow, but they must not replace the plain-language explanation.

If you discover that previous agent work introduced an unapproved product assumption:

**say so clearly.**

Do not defend an accidental architecture merely because time was already spent building it.

# 24. Decision logging

Material product decisions should be recorded in project documentation or an ADR.

Especially record decisions affecting:

- induction;
- member identity;
- birthdays/age;
- memory;
- personality analysis;
- listening scope;
- DMs;
- cross-member behavior;
- admin controls;
- privacy/reveal behavior;
- OpenAI architecture;
- persona;
- deployment.

An agent assumption does not become an approved decision simply because it appears in a pull request.

# 25. Testing philosophy

Tests protect approved behavior.

Tests must not fossilize obsolete product mistakes.

Maintain coverage for:

- database integrity;
- migrations;
- queue ownership;
- retries;
- TTL;
- edit races;
- deletion;
- source authorization;
- secret handling;
- admin boundaries;
- retrieval correctness;
- duplicate/correction behavior;
- internal gossip/evidence bookkeeping where it matters to memory administration;
- contradictions;
- Discord payload limits;
- feature configuration;
- persona-critical behavior where practical, including intentional social unreliability.

Also add permissiveness regressions where necessary so future agents do not gradually rebuild censorship or epistemic sanitization the owner explicitly removed.

Do not create tests whose only purpose is to force mass-market politeness, token austerity, courtroom-style factual caution, or generic sanitization into a tiny private-server product.

# 26. Documentation discipline

Whenever a product or architecture assumption changes, inspect and reconcile at minimum:

- `AGENTS.md`;
- README;
- relevant `docs/`;
- `.env.example`;
- affected service documentation;
- affected tests;
- PR body;
- rollout/rollback notes.

Do not leave mutually contradictory project doctrine scattered throughout the repository.

# 27. Quality gates

Before final review:

```bash
ruff check .
pytest
```

Plus any relevant integration or migration tests.

Where a live Discord test is required and cannot be automated, document it explicitly as:

`LIVE VALIDATION PENDING`

rather than pretending mocked CI proved live Discord behavior.

# 28. Phase discipline

The current broad build sequence is:

1. Foundation reconciliation — completed.
2. Memory architecture — completed.
3. Memory administration — completed.
4. Automatic memory extraction — **BUILT + TESTED + IN REVIEW** in the current stacked PR sequence; not merged.
5. Context intelligence / retrieval — **BUILT + TESTED + IN REVIEW** in the current stacked PR sequence; not merged.
6. Wilhelmina's memory-aware chat brain — **Phases 6A and 6B BUILT + TESTED + IN REVIEW; Phase 6C current work** for bounded short-term continuity and reliability; not merged.
7. Hardening, deployment, broader listening pathway, and final operational readiness.

Additional work required before or alongside later phases includes:

- removing accidental product assumptions discovered during audit;
- aligning persona/privacy/product doctrine;
- deliberately designing the evolving personality-analysis layer;
- resolving explicit product decisions such as the current project-level 18+ gate;
- production deployment, backups, monitoring, recovery, and live validation.

Do not skip dependency order merely because a later feature is more exciting unless the product owner explicitly approves parallel work.

# 29. Optimization priorities

When tradeoffs are required, prefer this order unless the product owner says otherwise:

1. Product intent.
2. Character fidelity.
3. Correctness.
4. Memory/context quality.
5. Reliability and data integrity.
6. Security of actual credentials/authorization.
7. User experience inside the intended tiny server.
8. Maintainability.
9. Latency where it harms the experience.
10. Token/cost efficiency.

For this project, **token minimization is deliberately near the bottom**.

Do not invert this list simply because common AI engineering advice targets products with millions of requests.

# 30. Core working principle

When choosing between:

**A.** faithfully implementing the product the owner actually described;

and

**B.** inventing a more conservative, sanitized, cheap, mass-market, reviewer-friendly, conventional, or enterprise-style product;

choose **A** unless a genuine mandatory constraint prevents it.

When a genuine mandatory constraint prevents it:

> **Explain the constraint. Do not pretend the owner asked for the compromise.**

And remember the actual deployment context:

> **This is a tiny private Discord server. Build Wilhelmina for the people who will actually be there, not for an imaginary audience of strangers.**