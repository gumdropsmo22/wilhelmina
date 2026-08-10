# AGENTS.md

## Operating rules

- Build from the latest target branch before starting a new tranche.
- Keep architecture decisions explicit in project documentation and pull-request scope.
- Do not revive `cogs.oracles`, `utils.persona`, or an Oracle umbrella module.
- Keep the active pattern: one feature equals one cog and one reusable service boundary when shared logic exists.
- Add or update tests with every behavior change.
- Update README, `.env.example`, and ADR or feature documentation whenever architecture or runtime configuration changes.
- Do not commit secrets, tokens, database files, or live Discord identifiers.
- Preserve backward-compatible service helpers unless a migration plan explicitly removes them.

## Current authorized scope

Allowed:

```txt
SQLite persistence
guild_config and audit_log storage
Covenant Gate and Coven Registry
scheduled broadcasts
Memory Ledger persistence and private administration
OpenAI integration behind explicit feature and privacy gates
versioned adult memory consent
interaction-scoped memory collection after extractor/event review
memory-aware designated server chat
memory-aware direct conversations with Wilhelmina
cross-member ordinary social memory use inside approved memory-aware contexts
tests and documentation
```

Not allowed without a separate approved tranche or required platform clearance:

```txt
server takeover
channel archival
server transformation
automatic mass role/channel mutation
new Oracle umbrella
tarot/readings/ritual expansion outside their own approved feature work
unreviewed public exposure of raw private Memory Ledger records
ambient whole-server memory collection without every required runtime/platform gate
committing or logging API keys, Discord tokens, prompts, responses, or prohibited private data
letting model output directly authorize access or perform destructive database changes
```

## Memory Ledger rules

- SQLite is the canonical memory store. OpenAI never owns or authorizes memory state.
- Automatic collection defaults off. The approved near-term collection mode is eligible human interaction involving Wilhelmina: direct conversation, DM, mention, reply, and later explicit remember actions.
- Broad ambient guild listening is a dormant future capability. It must remain fail-closed unless `MEMORY_COLLECTION_MODE=ambient`, `ENABLE_AMBIENT_MEMORY=true`, and a documented platform approval/clarification reference is configured.
- There is no history import or backfill.
- Only human-authored text is eligible. Bots, webhooks, automated integrations, attachments, media, and external-link contents are excluded.
- Prohibited information must be rejected locally before any external AI request or persistence.
- The sensitive-data guard includes credentials/secrets, financial/payment data, exact private addresses, government/private identifiers, medical or mental-health diagnoses, and comparable dangerous secrets.
- DMs directly involving Wilhelmina may be remembered after the current adult-memory disclosure is accepted. Third-party DMs Wilhelmina is not part of are never accessible or collectible.
- The current adult-memory disclosure is versioned. Legacy consent must not be silently upgraded to the newer DM/cross-member memory behavior.
- Ordinary social memories may be used across members in approved memory-aware server/DM contexts. Gossip must remain attributed and unverified. Admin-only/restricted material and prohibited secrets are never social ammunition.
- The current interlocutor's full permitted active profile is core chat context. Later deterministic selection is for relevant cross-member memories, evidence, contradictions, and receipts; it is not a token-cost austerity mechanism.
- The trusted identity context may include both names, the full canonical birth date, and locally calculated current age after authorization and current consent checks.
- Ordinary same-topic corrections permanently replace the superseded memory and receipts. Exact duplicates merge receipts. Unrelated memories coexist. Contradictory gossip remains separate, attributed, and linked.
- Admin-authored memories use an admin receipt rather than fabricated Discord metadata.
- Model extraction returns typed proposals only. Python validates categories, permissions, duplicates, replacements, contradictions, and every database mutation.
- Any member data access/correction/deletion controls required by current platform terms override older compatibility assumptions about the legacy `memory_opt_out` field; the legacy field itself remains inert unless explicitly migrated.

## OpenAI rules

- Use the Responses API through the shared provider boundary; Discord event paths must use native async calls.
- Quality and character fidelity take priority over minimizing token/model spend.
- Default routing is GPT-5.6 Sol for general/chat generation and GPT-5.6 Terra for structured memory work unless repository evals justify a better workload-specific choice.
- Private member-memory/chat requests must use `store=false` and fail closed unless the deployment explicitly asserts an approved enhanced retention mode (`mam` or `zdr`).
- Provider retention configuration lives in the OpenAI project; environment values are deployment assertions, not a substitute for actual MAM/ZDR approval/configuration.
- Do not use OpenAI-hosted conversation state as Wilhelmina's permanent memory.
- Operational logs may record model, request ID, token usage, latency/status, and content-free identifiers. They must not contain prompts, responses, memory summaries, receipts, preferred names, or birth dates.
- Authorization, reveal scope, consent, age calculation, destructive actions, and database writes remain deterministic Python responsibilities.

## Character contract

- The server is adult-only and Wilhelmina is intentionally profane, sharp, confrontational, funny, and socially intrusive when useful.
- Target voice: mean enough to delight the room, sharp enough to feel intelligent, and still useful.
- Direct interactions receive a response. Ordinary designated-channel chatter may receive a spontaneous interjection only when Wilhelmina has something genuinely funny, useful, juicy, contradictory, or strongly relevant to add.
- DMs are the same continuous character and same permitted Memory Ledger, but the room mode is more candid, intimate, and detailed rather than sanitized.
- Adult character direction never converts passwords, financial data, exact addresses, restricted/admin data, or similar protected information into comedy material.

## Quality gates

Run before review:

```bash
ruff check .
pytest
```

A change is complete only when implementation, tests, docs, configuration examples, migration behavior, and rollback notes agree.
