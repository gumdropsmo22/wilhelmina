# Phase 6A Chat Contract and Discord Routing

Phase 6A builds the deterministic Discord-facing boundary for Wilhelmina's future memory-aware chat brain.

It does **not** generate a chat response yet. The Phase-6A cog recognizes approved interactions, resolves trusted member references, assembles the locally authorized Phase-5 memory context, applies the Discord-audience reveal boundary, and records content-free operational metadata. Phase 6B will add the private OpenAI response path on top of this contract.

## Status

Phase 6A is implemented behind `ENABLE_CHAT=false` on its stacked feature branch and remains unmerged while under review.

## Approved interaction surfaces

Phase 6A responds to the same interaction-scoped surfaces already approved for Wilhelmina-facing conversation:

| Discord source | Routed surface | Audience |
| --- | --- | --- |
| Direct DM to Wilhelmina | `dm` | `private_interlocutor` |
| Reply to Wilhelmina in the home guild | `reply` | `guild_visible` |
| Direct mention of Wilhelmina in the home guild | `mention` | `guild_visible` |
| Any eligible human text in the designated Wilhelmina channel | `designated_channel` | `guild_visible` |

Unaddressed messages outside the designated Wilhelmina channel are not chat interactions. Phase 6A does not activate ambient whole-server listening.

Messages from bots/webhooks, empty text, messages from another guild, and existing `!` prefix commands are ignored by the chat router.

When more than one guild trigger applies, the diagnostic surface precedence is reply, then mention, then designated channel. All three are still `guild_visible`, so the precedence changes only routing metadata, not memory authorization.

## Discord Message Content intent

`ENABLE_CHAT=true` requests Discord's Message Content gateway intent independently from Memory Ledger extraction. The intent is required for ordinary free-form messages in the designated Wilhelmina channel and must also be enabled for the bot application in Discord's Developer Portal where Discord requires it.

The runtime rule is:

```text
message_content = ENABLE_CHAT or ENABLE_MEMORY_EXTRACTION
```

Chat and memory extraction are separate features. Enabling chat does not enable automatic memory extraction, and enabling extraction is not required for chat routing.

## Feature flag

```env
ENABLE_CHAT=false
```

The default remains off. In Phase 6A, setting this flag to true loads `cogs.chat`, requests Message Content intent, and enables routing/context preparation only. It does not make an OpenAI chat request and does not send a generated chat reply.

## Designated Wilhelmina channel

Phase 6A deliberately reuses the existing Memory Ledger setting:

```text
memory_ledger_settings.wilhelmina_channel_id
```

There is no duplicate chat-channel configuration or new schema. The existing `/memory-admin set-channel` and `/memory-admin clear-channel` controls remain the source of truth for the designated Wilhelmina interaction channel.

The Memory Ledger collection pause is **not** a chat mute switch. `collection_enabled=false` pauses durable automatic collection but does not disable direct conversation routing or memory use for an already-authorized chat interaction.

## Audience-aware memory authorization

Phase 5 authorizes memory relative to the interlocutor. Phase 6 adds another fact: who can read Wilhelmina's eventual Discord response.

Phase 6A therefore applies this additional deterministic audience matrix after Phase-5 assembly and before any future model call:

| Memory | One-to-one DM | Guild-visible chat |
| --- | ---: | ---: |
| Current speaker `cross_member` | yes | yes |
| Current speaker `owner_only` | yes | **no** |
| Current speaker `admin_only` | no | no |
| Other member `cross_member` | relevant only | relevant only |
| Other member `owner_only` | no | no |
| Other member `admin_only` | no | no |

This is enforced locally in `services.chat`; it is not a prompt request to a model.

If the audience filter removes a memory, contradiction IDs are also trimmed so an allowed memory does not retain an internal pointer to a hidden memory.

All Phase-5 corruption and dangerous-secret defenses remain in force before this audience filter, including same-guild record/entity/receipt checks, invalid privacy/reveal-pair rejection, Admin-note invariants, and private-key/credential filtering.

## Trusted member references

Phase 5 accepts explicit member IDs as trusted retrieval input only when Discord-facing code resolves them deterministically. Phase 6A implements that boundary.

Allowed reference sources are:

- Discord-resolved user mentions;
- the author of a resolved replied-to message when that author is a Registry member;
- an exact Coven Mark such as `WTCH-0003` or `⛧WTCH-0003⛧`, resolved locally through the Coven Registry.

Every resolved member must exist in the home guild's Coven Registry. Wilhelmina's system entry, the current speaker, unknown IDs, and malformed/unknown Coven Marks are excluded.

Plain-language or fuzzy names are **not** resolved into member IDs. A future model cannot decide that the word `Alex` means a particular user and thereby widen the memory candidate set.

## Guild-local date and identity

Phase 6A derives the date used by Phase-5 trusted identity context from the configured guild timezone. If no guild configuration exists, the existing UTC default is used.

This preserves the current identity contract: full canonical birth date stays in trusted local identity context and age is calculated locally for the relevant date. Phase 6A does not change the existing under-18 behavior, which remains a separate `PRODUCT DECISION PENDING` item.

## Cog/service split

`cogs.chat` owns Discord event adaptation only:

```text
Discord Message
  -> ChatMessageEnvelope
  -> route_chat_message(...)
  -> resolve_referenced_member_ids(...)
  -> assemble_chat_memory_context(...)
  -> content-free context-prepared log
```

`services.chat` owns the reusable deterministic rules:

- surface routing;
- audience classification;
- trusted member-reference resolution;
- guild-local chat date;
- Phase-5 context delegation;
- DM versus guild-visible reveal filtering.

The cog does not own privacy rules and does not instantiate an OpenAI client.

## No provider call in Phase 6A

Phase 6A intentionally stops after authorized context preparation.

It does not:

- call OpenAI;
- use `services.persona.render_persona_text`;
- send a generated Discord response;
- create provider-managed conversation state;
- persist raw chat turns;
- add streaming;
- add image generation;
- add semantic/vector retrieval;
- implement the separately policy-gated permanent/evolving personality dossier.

An explicit `chat` Persona Engine profile is added now so later Phase-6 work does not accidentally fall back to the `help` profile. The profile's future Discord output ceiling is 1,900 characters.

## Operational logging

Phase 6A logs no message content, identity profile text, memory summaries, receipt excerpts, birth dates, or generated responses.

A successful route records only operational metadata such as:

- guild/message/author IDs;
- selected surface and audience class;
- count of trusted referenced members;
- speaker-memory count;
- contextual-memory count.

Failures log a reason/category and exception type without private content.

## Tests

Phase-6A regression coverage includes:

- DM, designated-channel, mention, and reply routing;
- wrong-guild/unaddressed/bot/webhook/empty/prefix-command rejection;
- Message Content intent independence between chat and extraction;
- exact Registry/Coven-Mark reference resolution;
- refusal to fuzzy-resolve plain names;
- guild-local date rollover;
- `owner_only` present in DM context;
- `owner_only` removed from guild-visible context;
- other-member `cross_member` context preserved;
- contradiction pointers trimmed when a linked hidden memory is removed;
- Memory Ledger collection pause does not disable chat context;
- chat cog prepares context without sending a response;
- explicit chat Persona profile and disabled-by-default configuration.

Required repository gates remain:

```bash
ruff check .
pytest
```

No live OpenAI validation applies to Phase 6A because the tranche intentionally has no provider call.

A real Discord canary remains later rollout work; mocked/unit CI does not prove Developer Portal intent configuration or live Gateway delivery.

## Rollback

Phase 6A adds no database schema and no durable chat-content store.

Runtime rollback is:

```env
ENABLE_CHAT=false
```

Then restart Wilhelmina. Phase-5 memory state, extraction state, Registry data, identity data, and existing designated-channel configuration remain untouched.
