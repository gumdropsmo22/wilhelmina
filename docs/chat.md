# Phase 6 Chat Contract and Memory-Aware Responses

Phase 6 turns the authorization-first memory/context stack into Wilhelmina's live conversational brain. Phase 6A established deterministic Discord routing and audience-aware memory authorization. Phase 6B adds the private OpenAI response path while keeping local code authoritative for routing, reveal scope, identity, and secret handling.

## Status

Phase 6A is built, tested, and in review. Phase 6B is built on top of it and remains unmerged while exact-head validation/review proceeds.

## Approved interaction surfaces

| Discord source | Routed surface | Audience |
| --- | --- | --- |
| Direct DM to Wilhelmina | `dm` | `private_interlocutor` |
| Reply to Wilhelmina in the home guild | `reply` | `guild_visible` |
| Direct mention of Wilhelmina in the home guild | `mention` | `guild_visible` |
| Eligible human text in the designated Wilhelmina channel | `designated_channel` | `guild_visible` |

Unaddressed messages outside the designated channel remain excluded. Bots, webhooks, empty text, wrong-guild traffic, and existing `!` prefix commands are ignored. Phase 6B does not activate ambient whole-server listening.

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

Chat deliberately reuses:

```text
memory_ledger_settings.wilhelmina_channel_id
```

There is no duplicate chat-channel setting or schema. `/memory-admin set-channel` and `/memory-admin clear-channel` remain the source of truth. Memory collection pause/resume controls durable extraction, not whether Wilhelmina may converse using already-authorized memory.

## Audience-aware memory authorization

Phase 5 authorizes memory relative to the interlocutor. Phase 6 additionally authorizes it relative to the Discord audience before anything is sent to the model:

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

Plain or fuzzy names never become member IDs for authorization. The model does not resolve member identity for retrieval authority.

## Prompt construction

`services.chat_response` builds one stateless prompt from:

1. Wilhelmina's canonical `BASE_VOICE`;
2. the shared global limits;
3. chat-specific behavior and epistemic rules;
4. the locally classified Discord surface/audience;
5. `render_memory_context_for_prompt(...)`, including trusted identity and only authorized memory/evidence;
6. the current member message;
7. a user-facing Discord-only response contract capped by the `chat` persona profile at 1,900 characters.

Memory and receipt excerpts are explicitly marked as **data, never instructions**. Prompt injections or policy claims stored inside memories/evidence do not become authority. Facts may be stated as facts; Inferences and Impressions remain qualified; Gossip remains unverified; contradictions are not silently resolved when the supplied evidence does not establish a winner.

Wilhelmina should use relevant memory naturally instead of announcing that she queried a ledger, database, profile, or receipt system.

## Current-message secret guard

The current Discord message is validated locally **before** an OpenAI request. The deterministic hard-secret boundary rejects credentials and other concrete security hazards already protected by the memory system, plus recognizable private-key formats including:

- generic PEM and encrypted/typed private keys;
- OpenPGP private-key blocks;
- PuTTY key-file headers;
- SSH2 private-key headers.

A rejected current message is not sent to the provider and receives the deterministic chat fallback. This is a credential/security boundary, not a general sensitive-topic filter.

## OpenAI provider boundary

Phase 6B reuses `services.ai`; the chat cog does not instantiate its own OpenAI client.

The provider path is:

```text
cogs.chat
  -> services.chat_response.generate_chat_reply_async(...)
  -> services.ai.generate_private_result_async(...)
  -> workload = chat
```

Private chat requires the existing deployment assertion `OPENAI_RETENTION_MODE=mam` or `zdr`, uses the configurable chat-model route, and forces provider response storage off through the existing private provider configuration. Provider state is not used as Wilhelmina's canonical memory.

Phase 6B does **not** use provider-managed conversation IDs or `previous_response_id`; every request is constructed from local authorized state.

## Discord output behavior

Generated text:

- preserves intentional paragraphs;
- normalizes stray whitespace;
- is clipped to 1,900 characters;
- is sent as a reply to the triggering message;
- suppresses automatic author pings;
- uses `AllowedMentions.none()` so generated text cannot ping users, roles, or `@everyone`.

Provider/privacy/unavailable/empty failures use the deterministic `chat` Persona fallback. Operational logs record only IDs, routing/audience, counts, provider status/model/request ID, failure categories, and exception types—not prompts, response text, memory summaries, evidence, birth dates, or message content.

## Conversation continuity

Phase 6B is intentionally **stateless between turns** beyond the durable Memory Ledger/context system. It does not create a transcript table or provider-managed conversation state.

Phase 6C adds bounded short-term conversational continuity and reliability controls on top of this response path. That short-term layer must not become a hidden permanent transcript/profile system or a new authorization source.

## Tests

Automated coverage includes:

- all Phase-6A routing/audience/reference regressions;
- Persona + identity + authorized memory + current-message prompt layering;
- explicit data-not-instructions and epistemic prompt rules;
- DM/guild audience contracts;
- current-message credential/private-key rejection before provider use;
- private `chat` workload routing and enhanced-retention requirement;
- deterministic provider/privacy failure fallbacks;
- output line-break preservation and 1,900-character clipping;
- Discord reply behavior and mention suppression;
- proof that unaddressed guild chatter does not generate a response.

Required gates remain:

```bash
ruff check .
pytest
```

No live OpenAI key/provider request is used by CI. Live Discord/provider validation remains later rollout work and must be reported as `LIVE VALIDATION PENDING` until performed.

## Rollback

Phase 6B adds no database schema and no durable chat transcript.

Runtime rollback is:

```env
ENABLE_CHAT=false
```

Then restart Wilhelmina. Memory Ledger, extraction queues, Registry/identity state, and designated-channel configuration remain untouched.

## Explicit non-scope

Phase 6B does not add:

- ambient whole-server listening;
- permanent transcript storage;
- provider-managed canonical memory;
- streaming;
- image generation;
- a new consent/version gate;
- changes to the unresolved under-18 behavior;
- the separately policy-gated permanent/evolving personality dossier.
