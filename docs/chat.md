# Phase 6 Memory-Aware Chat

Phase 6 turns Wilhelmina's authorization-first Memory Ledger into live conversation. Phase 6A establishes deterministic Discord routing and audience-aware reveal rules. Phase 6B builds the private OpenAI prompt/response path. Phase 6C adds bounded local conversation continuity and duplicate/concurrency/edit/delete/restart reliability.

## Status

Phases 6A and 6B are built, tested, and in review in the stacked PR sequence. Phase 6C is built on top of them and remains unmerged while exact-head validation and review proceed.

## Approved interaction surfaces

| Discord source | Routed surface | Audience |
| --- | --- | --- |
| Direct DM to Wilhelmina | `dm` | `private_interlocutor` |
| Reply to Wilhelmina in the home guild | `reply` | `guild_visible` |
| Direct mention of Wilhelmina in the home guild | `mention` | `guild_visible` |
| Eligible human text in the designated Wilhelmina channel | `designated_channel` | `guild_visible` |

Unaddressed messages outside the designated channel remain excluded. Bots, webhooks, empty text, wrong-guild traffic, and existing `!` prefix commands are ignored. Phase 6 does not activate ambient whole-server listening.

## Message Content intent and feature flag

`ENABLE_CHAT=true` loads `cogs.chat` and requests Discord's Message Content intent independently from automatic memory extraction:

```text
message_content = ENABLE_CHAT or ENABLE_MEMORY_EXTRACTION
```

The intent must also be enabled in Discord's Developer Portal where required.

```env
ENABLE_CHAT=false
```

Chat remains disabled by default. Enabling chat does not enable automatic memory extraction and does not resume the Memory Ledger collection gate.

## Designated channel

Chat reuses the existing setting:

```text
memory_ledger_settings.wilhelmina_channel_id
```

There is no duplicate chat-channel setting or schema. `/memory-admin set-channel` and `/memory-admin clear-channel` remain the source of truth. Memory collection pause/resume controls durable extraction, not whether Wilhelmina may converse using already-authorized memory.

## Audience-aware memory authorization

Phase 5 authorizes memory relative to the interlocutor. Phase 6 additionally authorizes it relative to the Discord audience before anything reaches the model:

| Memory | One-to-one DM | Guild-visible chat |
| --- | ---: | ---: |
| Current speaker `cross_member` | yes | yes |
| Current speaker `owner_only` | yes | **no** |
| Current speaker `admin_only` | no | no |
| Other member `cross_member` | relevant only | relevant only |
| Other member `owner_only` | no | no |
| Other member `admin_only` | no | no |

The model cannot widen this matrix. Hidden contradiction pointers are trimmed with hidden memories. Phase-5 same-guild checks, Admin-note invariants, receipt/entity corruption defenses, and credential/private-key filters remain in force.

## Trusted member references

Cross-member retrieval may be widened only by locally authenticated references:

- Discord-resolved mentions;
- the author of a resolved replied-to message when that author is a Registry member;
- an exact Coven Mark such as `WTCH-0003` or `⛧WTCH-0003⛧`.

Plain or fuzzy names never become member IDs for authorization. Neither the model nor short-term chat history may resolve member identity for retrieval authority.

## Prompt construction

`services.chat_response` builds each provider request from:

1. Wilhelmina's canonical `BASE_VOICE`;
2. the shared global limits;
3. chat-specific behavior rules;
4. the locally classified Discord surface/audience;
5. `render_memory_context_for_prompt(...)`, including trusted identity and only authorized memory/evidence;
6. bounded recent conversation history when present;
7. the current member message;
8. a user-facing Discord-only response contract capped by the `chat` persona profile at 1,900 characters.

Memory, evidence, and recent conversation history are explicitly **data, never authorization**. Prompt injections or policy claims inside any of those sections do not change reveal scope, source authorization, Discord audience, or member identity.

### Intentional social unreliability

Wilhelmina is **not** meant to behave like a courtroom transcript or a careful fact-checker in ordinary social chat. The owner has explicitly defined playful misinformation and confusing interpersonal recall as part of her character. For ordinary member-to-member chatter she may deliberately or casually:

- misremember who said something;
- merge two conversations together;
- exaggerate a detail;
- confidently repeat the wrong version;
- play contradictory memories against each other;
- embellish harmless connective details when it makes the interaction funnier or messier.

Fact / Inference / Impression / Gossip labels remain useful internal context, but they are not a requirement that the user-facing reply faithfully preserve epistemic labels or carefully qualify every rumor. The goal is **playful social chaos, not faithful meeting minutes**.

That creative freedom does **not** widen any hard boundary. It may never be used to invent or expose credentials, private keys, payment credentials, identity-document numbers, doxxing-grade addresses, `admin_only` material, hidden `owner_only` material in guild-visible chat, unauthorized guild/member data, commands, permissions, destructive actions, or server state.

Wilhelmina should use relevant memory naturally instead of announcing that she queried a ledger, database, profile, or receipt system.

## Current-message, memory-context, and history secret guard

The current Discord message, the rendered authorized memory context, and recent short-term history are validated locally **before** an OpenAI request. The deterministic hard-secret boundary rejects concrete credential/security hazards already protected by the memory system, including recognizable private-key formats and credential-bearing connection URLs such as `scheme://user:password@host` and password-only user-info forms.

Recognizable private-key coverage includes:

- generic PEM and encrypted/typed private keys;
- OpenPGP private-key blocks;
- PuTTY key-file headers;
- SSH2 private-key headers.

Rejected text is not sent to the provider and receives deterministic fallback copy. Successfully generated member/assistant text is rechecked before it is admitted to short-term history. This is a credential/security boundary, not a general sensitive-topic filter.

## OpenAI provider boundary

The chat path reuses `services.ai`; the cog does not instantiate its own OpenAI client:

```text
cogs.chat
  -> services.chat_response.generate_chat_reply_async(...)
  -> services.ai.generate_private_result_async(...)
  -> workload = chat
```

Private chat requires the existing deployment assertion `OPENAI_RETENTION_MODE=mam` or `zdr`, uses configurable chat-model routing, and forces provider response storage off through the existing private provider configuration. Provider state is not Wilhelmina's canonical memory.

Phase 6 does **not** use provider-managed conversation IDs or `previous_response_id`; every request is reconstructed from local authorized state.

## Discord output behavior

Generated text:

- preserves intentional paragraphs;
- normalizes stray whitespace;
- is clipped to 1,900 characters;
- is sent as a reply to the triggering message;
- suppresses automatic author pings;
- uses `AllowedMentions.none()` so generated text cannot ping users, roles, or `@everyone`.

Provider/privacy/unavailable/empty failures use the deterministic `chat` Persona fallback. Operational logs record IDs, routing/audience, counts, provider metadata, history counts, and failure categories—not prompts, response text, memory summaries, evidence, birth dates, or message content.

## Phase 6C short-term conversation continuity

`services.chat_continuity.ChatContinuityRuntime` keeps only bounded **process-memory** continuity:

```text
maximum entries per conversation: 24
maximum content characters per conversation: 24,000
recent Discord message IDs retained for dedupe: 1,024
maximum simultaneous provider generations: 3
```

These are technical bounds against unbounded context growth and accidental provider storms, not token-austerity product rules.

The continuity boundary is audience-aware:

- DMs are isolated by the home guild + DM channel + interlocutor user;
- guild-visible history is isolated by the home guild + Discord channel;
- DM history never becomes guild history;
- history from one guild channel never enters another channel.

A guild channel's history may contain prior **Wilhelmina interactions in that same visible channel**, including different members, because those turns were already visible to that channel audience. Unaddressed ambient messages are never added because they never pass the chat router.

Only a provider-backed response that was successfully sent is paired with its triggering member message in short-term history. Deterministic provider-failure fallbacks are not treated as meaningful conversational state.

## Duplicate, ordering, and provider concurrency controls

Each accepted Discord message ID is claimed once in process memory before generation. A duplicate event for an inflight or recently completed message is ignored, preventing duplicate OpenAI calls and duplicate replies.

Each conversation key has an `asyncio.Lock`. Overlapping messages in the same DM/channel therefore generate serially, allowing the later message to see the prior completed exchange instead of racing it. Different conversations may proceed independently.

A process-local semaphore allows at most three simultaneous provider generations across the bot. Excess work waits rather than being silently dropped or creating an arbitrary punitive member rate policy.

If a Discord send fails, the message claim is released so a later duplicate delivery may retry. A successfully sent reply completes the dedupe claim.

## Edits and deletes

Short-term history tracks the triggering Discord message ID.

- deleting the source member message removes both that member turn and its paired Wilhelmina reply from future short-term history;
- editing the source member message updates only the member side of an existing turn;
- an edit does **not** regenerate the already-sent historical Wilhelmina reply;
- if edited text fails the deterministic secret guard, the whole ephemeral turn is removed rather than forwarding the newly unsafe text later.

These listeners reconcile only entries already admitted to the chat runtime. They do not create ambient collection or fetch Discord history that Wilhelmina never received.

## Restart behavior and persistence boundary

Phase 6C deliberately adds **no chat-history database table**. Restarting/reloading the bot resets:

- recent conversation history;
- duplicate-message state;
- conversation locks;
- provider concurrency state.

The durable Memory Ledger, Registry identity, configured designated channel, and extraction state remain unchanged and continue to provide long-term continuity after restart.

Permanent transcript storage or semantic retrieval over transcripts is a separate product/architecture decision and is not smuggled into Phase 6C.

## Tests

Automated coverage includes:

- all Phase-6A routing/audience/reference regressions;
- Phase-6B Persona + identity + memory + provider prompt behavior;
- intentional socially unreliable/chaotic recall language in the prompt contract;
- current-message, authorized-context, and recent-history credential/private-key rejection before provider use;
- private chat workload and enhanced-retention routing;
- deterministic provider/privacy fallbacks;
- output clipping and mention suppression;
- DM-vs-guild continuity key isolation;
- bounded entry/character history;
- bounded duplicate-message memory;
- exact-once duplicate event behavior;
- second-turn history reaching the next provider prompt;
- fallbacks not entering history;
- source edit/delete reconciliation;
- restart creating a fresh empty continuity runtime.

Required gates remain:

```bash
ruff check .
pytest
```

No live OpenAI key/provider request is used by CI. Live Discord/provider validation remains later rollout work and must be reported as `LIVE VALIDATION PENDING` until performed.

## Rollback

Phase 6C adds no database schema and no durable chat transcript.

Runtime rollback is:

```env
ENABLE_CHAT=false
```

Then restart Wilhelmina. Memory Ledger, extraction queues, Registry/identity state, and designated-channel configuration remain untouched. Restarting alone also clears all Phase-6C short-term history/dedupe state.

## Explicit non-scope

Through Phase 6C, chat still does not add:

- ambient whole-server listening;
- permanent transcript storage;
- semantic/vector transcript retrieval;
- provider-managed canonical memory;
- streaming;
- image generation;
- a new consent/version gate;
- changes to the unresolved under-18 behavior;
- the separately policy-gated permanent/evolving personality dossier.
