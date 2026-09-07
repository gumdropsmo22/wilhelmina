# Phase 6 Memory-Aware Chat

Phase 6 turns Wilhelmina's authorization-first Memory Ledger into live conversation.

- **6A — MERGED:** deterministic Discord routing, trusted member references, and audience-aware memory authorization.
- **6B — MERGED:** private provider-backed Wilhelmina responses.
- **6C — MERGED:** bounded local conversation continuity, dedupe, ordering, edit/delete reconciliation, and provider-concurrency control.
- **6D — BUILT + TESTED, REVIEW BLOCKERS RESOLVED:** hostile hardening of prompt authority, practical credential boundaries, generated output, and in-flight Discord source races; awaiting explicit merge authorization.
- **6E — PLANNED:** live Discord/provider rollout and behavioral validation.

## Approved interaction surfaces

| Discord source | Routed surface | Audience |
| --- | --- | --- |
| Direct DM to Wilhelmina | `dm` | `private_interlocutor` |
| Reply to Wilhelmina in the home guild | `reply` | `guild_visible` |
| Direct mention of Wilhelmina in the home guild | `mention` | `guild_visible` |
| Eligible human text in the designated Wilhelmina channel | `designated_channel` | `guild_visible` |

Unaddressed messages outside the designated channel remain excluded. Bots, webhooks, empty text, wrong-guild traffic, and existing `!` prefix commands are ignored. Phase 6 does not activate ambient whole-server listening.

`ENABLE_CHAT=true` loads `cogs.chat` and requests Discord Message Content intent independently from automatic memory extraction. Chat remains disabled by default. The intent must also be enabled in Discord's Developer Portal where required.

The designated chat channel reuses `memory_ledger_settings.wilhelmina_channel_id`; `/memory-admin set-channel` and `/memory-admin clear-channel` remain the source of truth. Pausing durable Memory Ledger extraction does not mute chat or prevent already-authorized memories from being used conversationally.

## Audience-aware memory authorization

Phase 5 authorizes memory relative to the interlocutor. Phase 6 additionally authorizes it relative to the Discord audience before provider use:

| Memory | One-to-one DM | Guild-visible chat |
| --- | ---: | ---: |
| Current speaker `cross_member` | yes | yes |
| Current speaker `owner_only` | yes | **no** |
| Current speaker `admin_only` | no | no |
| Other member `cross_member` | relevant only | relevant only |
| Other member `owner_only` | no | no |
| Other member `admin_only` | no | no |

Other-member raw receipt evidence is independently authorized instead of inheriting permission merely because its attached summary is `cross_member`. A DM from member A therefore cannot smuggle member B's raw private DM text through a public sibling memory. Guild-visible prompts likewise refuse raw evidence from source messages that also back owner/admin/restricted material.

The model cannot widen this matrix. Phase-5 guild checks, Admin-note invariants, corrupted entity/receipt defenses, contradiction trimming, and retrieval-time secret guards remain in force.

## Trusted member references

Cross-member retrieval may be widened only by locally authenticated references:

- Discord-resolved mentions;
- the author of a resolved replied-to message when that author is a Registry member;
- an exact Coven Mark such as `WTCH-0003` or `⛧WTCH-0003⛧`.

Plain or fuzzy names never become member IDs for authorization. Neither the model nor short-term chat history may create retrieval authority.

## Intentional social unreliability

Wilhelmina is not a courtroom transcript. Ordinary social unreliability is an approved part of the character.

She may, for entertainment inside the intended tiny private server:

- misremember who said something;
- merge conversations together;
- exaggerate a detail;
- confidently repeat the wrong version;
- play contradictions against each other;
- embellish harmless connective details.

Fact / Inference / Impression / Gossip remain useful internal context labels, but user-facing chat does not have to reproduce them faithfully or qualify every rumor. This social freedom does **not** widen actual credential, `admin_only`, hidden `owner_only`, guild-isolation, command, destructive-action, or permission boundaries.

## Phase 6D provider authority boundary

Phase 6D separates trusted model instructions from untrusted conversational data using the OpenAI Responses API's native authority channels.

`services.chat_response.build_chat_instructions(...)` contains only trusted local material:

- canonical `BASE_VOICE`;
- global Persona limits;
- chat behavior rules, including the approved chaotic social style;
- locally classified interaction surface and Discord audience;
- hard authorization/security rules;
- Discord response-format/length contract.

Those rules are sent through the Responses API `instructions` parameter, which is a system/developer-authority message.

The ordinary provider `input` contains only locally authorized conversational data:

- rendered Memory Ledger context;
- bounded recent conversation history;
- the current member message.

Each payload is JSON-quoted before interpolation and labeled as untrusted data. A member, memory excerpt, or history turn may contain text such as `RESPONSE CONTRACT`, fake XML tags, or `CHAT BEHAVIOR RULES`; that text remains data and cannot syntactically become a peer developer/system section.

The shared `services.ai` boundary accepts optional `instructions` while preserving the old request shape for every caller that does not use them. Private chat still uses workload routing, enhanced-retention assertion, and `store=false`.

## Practical credential boundary

Chat secret handling protects concrete credentials/security material rather than banning ordinary topic words or attempting enterprise-grade PII loss prevention.

Recognizable blocked forms include:

- common provider/API/auth tokens;
- labelled credential values such as `password: <value>` or `api key = <value>`;
- bare/possessive password assignments where the text clearly supplies an actual credential value;
- credential-bearing connection URLs such as `scheme://user:password@host` and password-only user-info forms;
- PEM/OpenPGP, PuTTY, and SSH2 private-key forms;
- Luhn-valid payment-card numbers and CVV-style values;
- labelled banking credential values.

Common Discord Markdown wrappers are normalized in a scan-only copy so inline code cannot trivially hide an otherwise obvious credential. Ordinary sentences such as discussing password managers or needing to renew a passport are not credentials merely because they contain those words.

The current message, authorized memory context, recent history, and generated model output are all scanned locally at their provider/Discord boundaries. A model-generated credential therefore fails closed to deterministic fallback **before Discord delivery** and is not admitted to continuity history. Full model output is scanned before Discord-length clipping and the clipped result is scanned again.

Existing simple identity-number/private-address safeguards may remain, but Phase 6D is explicitly **not** a generalized PII/DLP system. The owner does not want the tranche held open for increasingly theoretical SSN/address/personal-information formatting variants absent a concrete access risk or binding external/platform requirement.

This is a practical security boundary, not a general sensitive-topic or compliance filter.

## OpenAI provider boundary

The chat path remains:

```text
cogs.chat
  -> services.chat_response.generate_chat_reply_async(...)
  -> services.ai.generate_private_result_async(...)
  -> Responses API, workload=chat
```

The cog does not instantiate a separate provider client. Private chat requires the configured MAM/ZDR deployment assertion used by the repository's private provider policy and forces response storage off. That environment value is only a deployment assertion; it does not itself grant an OpenAI retention entitlement.

Phase 6 does not use provider-managed conversation IDs or `previous_response_id`. Every request is reconstructed from local authorized state.

## Discord output behavior

Generated text:

- preserves intentional paragraphs;
- normalizes stray whitespace;
- is clipped to 1,900 characters;
- is practical-hard-secret scanned before delivery;
- is sent as a reply to the triggering message;
- suppresses automatic author pings;
- uses `AllowedMentions.none()` so generated text cannot ping users, roles, or `@everyone`.

Provider/privacy/unavailable/empty/output-rejected failures use deterministic `chat` Persona fallback. Operational logs contain IDs, routing/audience, counts, model/request metadata, and failure categories—not prompts, response text, memory summaries, evidence, birthdays, or Discord message content.

## Short-term continuity

`services.chat_continuity.ChatContinuityRuntime` keeps only bounded process-memory continuity:

```text
maximum entries per conversation: 24
maximum content characters per conversation: 24,000
recent Discord message IDs retained for dedupe: 1,024
maximum simultaneous provider generations: 3
```

DM histories are isolated per interlocutor. Guild-visible history is isolated per guild channel. Only provider-backed responses that were successfully sent become continuity; deterministic fallbacks do not.

Duplicate Discord message IDs are claimed once in process memory. Each conversation uses an `asyncio.Lock`, so overlapping messages in the same conversation serialize. A process-local semaphore allows at most three simultaneous provider generations across conversations.

Restart intentionally clears history, dedupe state, source-mutation tombstones, locks, and the concurrency runtime. The durable Memory Ledger remains canonical long-term state. There is no permanent chat transcript table.

## Edits, deletes, and in-flight generation

Phase 6C reconciled edits/deletes after a turn had entered continuity. Phase 6D closes the adjacent race where the Discord source changes **while the provider is still generating**.

The runtime maintains a bounded process-local source-mutation map:

- safe edit -> latest safe member text;
- delete or unsafe edit -> tombstone.

If a delete or credential-bearing unsafe edit arrives while generation is in flight, the tombstone wins over the stale original event snapshot. The stale reply is suppressed before Discord send and no stale exchange enters history.

If a safe edit arrives while generation is in flight, the already-generated reply may still be sent under the established no-regeneration contract, but the eventual continuity record uses the latest safe member text rather than the stale event snapshot.

Existing post-send behavior remains:

- deleting the source removes both sides of the ephemeral turn from future history;
- safe editing rewrites only the member side;
- edits do not retroactively regenerate Wilhelmina's already-sent reply;
- unsafe edits remove/tombstone the turn.

## Tests

Automated hostile coverage includes:

- routing/audience/reference authorization regressions;
- cross-member raw-evidence authorization in both guild and DM contexts;
- current-message, context, history, and output practical-credential rejection;
- benign credential-topic language remaining conversationally usable;
- Markdown-wrapped concrete credential detection;
- JSON quoting of fake section headings/instructions;
- Responses `instructions` forwarding with `store=false` preserved;
- the chat persona/security contract living in provider instructions rather than user/data input;
- duplicate-event suppression;
- bounded DM/guild continuity and concurrency;
- source edit/delete reconciliation;
- delete/unsafe-edit races during in-flight generation;
- safe edits winning over stale source snapshots;
- restart clearing all ephemeral chat state;
- mention suppression and Discord output bounds.

Required gates:

```bash
ruff check .
pytest
```

No live OpenAI request is used by CI. Live Discord/provider validation remains **LIVE VALIDATION PENDING** until Phase 6E.

## Rollback

Phase 6D adds no database schema and no durable transcript. Runtime rollback remains:

```env
ENABLE_CHAT=false
```

Then restart Wilhelmina. Memory Ledger data, extraction queues, Registry/identity state, and designated-channel configuration remain untouched.

## Explicit non-scope

Through Phase 6D, chat still does not add:

- ambient whole-server listening;
- permanent transcript storage;
- semantic/vector transcript retrieval;
- provider-managed canonical memory;
- streaming;
- image generation;
- a new consent/version gate;
- changes to the unresolved under-18 behavior;
- the separately policy-gated permanent/evolving personality dossier.
