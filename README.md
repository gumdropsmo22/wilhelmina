# Wilhelmina Bot

Wilhelmina is a Python Discord bot built with `discord.py` for a dedicated home server. The project is moving toward modular onboarding, AI-backed interactions, administrative tools, scheduled messaging, and server community workflows.

## Runtime model

Wilhelmina is configured for a **brand-new dedicated Discord server**.

Existing-server takeover, channel archival, and automatic server transformation are not supported runtime modes. The bot should be invited into its home guild, configured with `HOME_GUILD_ID`, and expanded through feature-flagged cogs.

## Feature architecture

Features are independent modules. There is no umbrella `oracles` cog in the active runtime.

Current cogs:

```txt
cogs.core               /about, /uptime
cogs.admin              /admin diagnostics, /admin features, /admin sync, /admin config ...
cogs.help               /help
cogs.rules              /rules, /rules-admin ...
cogs.memory_admin       /memory-admin ...
cogs.memory_extraction  interaction-scoped automatic Memory Ledger extraction
cogs.invite             /invite
cogs.roll               /roll
cogs.eight_ball         /8ball
cogs.fortune            /fortune
cogs.broadcasts         /broadcast-admin ...
```

Each optional feature has its own flag:

```env
ENABLE_HELP=true
ENABLE_RULES=true
ENABLE_MEMORY_ADMIN=true
ENABLE_MEMORY_EXTRACTION=false
ENABLE_INVITE=false
ENABLE_ROLL=false
ENABLE_EIGHT_BALL=false
ENABLE_FORTUNE=false
ENABLE_BROADCASTS=false
```

`ENABLE_ORACLES` is retained only as a temporary compatibility shim for old `.env` files. New configuration should not use it.

## Prerequisites

- Python 3.11+
- Git
- A Discord application with bot token and client ID
- A dedicated Discord server/guild for Wilhelmina

## Installation

```bash
git clone https://github.com/gumdropsmo22/wilhelmina.git
cd wilhelmina
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS/Linux
source .venv/bin/activate
```

Install runtime and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ai]"
```

Legacy install path:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Copy the example environment file and fill in real values:

```bash
cp .env.example .env
```

Minimum development configuration:

```env
DISCORD_TOKEN=
CLIENT_ID=
SERVER_MODE=dedicated
HOME_GUILD_ID=
COMMAND_SYNC_MODE=guild
DATABASE_PATH=data/wilhelmina.sqlite3
ENABLE_CORE=true
ENABLE_ADMIN=true
ENABLE_HELP=true
ENABLE_RULES=true
ENABLE_MEMORY_ADMIN=true
```

`DEV_GUILD_ID` is accepted as a legacy alias for `HOME_GUILD_ID`, but new setups should use `HOME_GUILD_ID`.

## SQLite persistence

Wilhelmina stores dedicated-server configuration, administrative audit events, onboarding state, rules versions, rules acceptance records, broadcast state, private identity data, and the Memory Ledger in SQLite.

```env
DATABASE_PATH=data/wilhelmina.sqlite3
```

Relative paths resolve from the repository root. The SQLite file is local runtime state and should be backed up before deployment moves, schema changes, or manual database edits.

Current persistence stores include:

```txt
guild_config
audit_log
onboarding_state
rules_versions
rules_acceptance
broadcast_settings
broadcast_runs
broadcast_text_history
coven_registry_entries
coven_profile_shells
coven_member_identity_profiles
memory_ledger_settings
memory_records
memory_receipts
memory_contradictions
memory_entities
memory_search
memory_extraction_jobs
schema_migrations
```

The stored guild configuration is the source of truth for server role/channel IDs after Phase 2. Environment variables for role/channel IDs are not used by the new config layer.

## Living Command Grimoire

`/help` opens Wilhelmina's dynamic public command grimoire. It reads the live slash-command tree, hides admin tooling, groups public commands into categories, and can show sealed future doors such as tarot, readings, rituals, welcome, and broadcast.

The grimoire uses the Persona Engine's `help` feature profile for short AI-polished intro text when `OPENAI_API_KEY` is configured. If AI is unavailable, it falls back to deterministic copy.

## Covenant Gate rules UI

`/rules` opens the active rules covenant for a user and lets them accept it through a button. Acceptance is stored with the user ID, guild ID, active rules version, method, and timestamp.

Admin commands:

```txt
/rules-admin set
/rules-admin activate
/rules-admin preview
/rules-admin publish
/rules-admin summary
/rules-admin user
/rules-admin list
```

The Covenant Gate records acceptance only. It does **not** assign roles, mutate permissions, or transform the server. Later role automation can consume the stored acceptance records safely.

## Admin config commands

The `/admin config` commands are administrator-only and always respond ephemerally.

```txt
/admin config view
/admin config set-role
/admin config set-channel
/admin config set-timezone
/admin config validate
/admin config clear
```

These commands only store, clear, validate, and audit configuration. They do **not** create roles, create channels, assign roles, onboard users, mutate permissions, schedule jobs, or transform a server.

## Memory Ledger admin controls

`cogs.memory_admin` adds the private `/memory-admin` surface. It is restricted to administrators in `HOME_GUILD_ID`, and every response is ephemeral.

Core commands:

```txt
/memory-admin status
/memory-admin pause
/memory-admin resume
/memory-admin set-channel
/memory-admin clear-channel
/memory-admin profile
/memory-admin show
/memory-admin receipts
/memory-admin search
/memory-admin add
/memory-admin edit
/memory-admin delete
/memory-admin member-data
/memory-admin member-data-id
/memory-admin delete-member
/memory-admin delete-member-id
```

The persistent pause/resume switch is separate from `MEMORY_COLLECTION_MODE`. Resuming the local gate does not activate automatic extraction by itself. Search and inspection are local SQLite operations; Phase 3 does not call OpenAI and does not need an API key.

Exact duplicate admin writes still merge receipts. Their privacy metadata may tighten but never loosen: a later restricted/admin-only confirmation can narrow an existing ordinary record, while a broader duplicate cannot reopen a record that is already narrower. The command reports the actual stored privacy/reveal scope and importance.

Single-memory deletion requires the exact confirmation text `DELETE`. Member-wide Memory Ledger deletion requires `DELETE MEMBER`. The member-wide purge removes the member's own Memory Ledger records **and** receipts they authored on other members' memories. Any memory left with zero evidence is also deleted; memories that still have another receipt survive. The purge deliberately does **not** silently delete Coven Registry or private identity/consent rows.

`member-data-id` and `delete-member-id` provide the same private controls for departed/archived users who are no longer selectable as `discord.Member`.

See `docs/memory_controls.md` and `docs/memory_ledger.md` for the privacy and data-control contract.

## Automatic Memory Ledger extraction

`cogs.memory_extraction` is the Phase 4 interaction-scoped ingestion worker. It is **disabled by default** and does not enable broad whole-server listening.

When explicitly enabled, eligible human text is limited to direct DMs with Wilhelmina, the designated Wilhelmina chat, direct mentions, and resolvable replies to Wilhelmina. Unaddressed ambient guild chatter remains excluded even if future ambient environment switches exist.

Minimum activation shape:

```env
ENABLE_MEMORY_EXTRACTION=true
MEMORY_COLLECTION_MODE=interaction
OPENAI_RETENTION_MODE=mam
```

`zdr` may be used instead of `mam` when that approved project configuration is available. The environment value is only a deployment assertion; the corresponding retention control must actually be configured for the OpenAI project. Private extraction requests use `store=false`.

Enabling extraction requests Discord's Message Content intent, which must also be enabled in the Discord Developer Portal. The persistent Memory Ledger collection gate must be resumed, and each author must have the current versioned adult-memory consent.

Phase 4 uses schema v11 queue ownership with per-claim tokens, absolute raw-text TTL cleanup, atomic authorization before queue persistence, uncached/raw edit handling, and deterministic sensitive-data rejection both before OpenAI and after structured model output. SQLite/Python remain authoritative; the model cannot authorize access or mutate memory directly.

For upgrades from the earlier v10 extraction draft, stop/drain old workers before enabling v11. v11 invalidates leftover tokenless processing rows and installs database enforcement that prevents old-style tokenless claims from entering `processing`.

See `docs/memory_extraction.md` for the full eligibility, privacy, queue, rollout, and rollback contract.

## Scheduled Daily Broadcasts

`cogs.broadcasts` adds `/broadcast-admin` controls for Wilhelmina's automatic daily show system.

Segments:

```txt
morning  The Vanguard Frequency   default 08:00 Asia/Riyadh
evening  W.W.N. Broadcast          default 21:30 Asia/Riyadh
```

Admin commands:

```txt
/broadcast-admin status
/broadcast-admin preview
/broadcast-admin send-test
/broadcast-admin enable
/broadcast-admin disable
/broadcast-admin set-channel
/broadcast-admin set-time
/broadcast-admin set-timezone
```

Broadcasts are disabled by default. The system stores schedule settings, run history, idempotency keys, and text-history hashes in SQLite. Until final news and astronomy providers are configured, previews and test sends use deterministic fallback copy and scheduled runs skip posting rather than inventing headlines or sky data.

Recommended first setup:

```env
ENABLE_BROADCASTS=true
```

Then run:

```txt
/broadcast-admin set-channel target:default channel:#your-channel
/broadcast-admin preview segment:morning
/broadcast-admin send-test segment:evening
/broadcast-admin enable segment:all
```

## Persona Engine

Wilhelmina has a central Persona Engine with one base voice and feature-specific **feature profiles**.

Current feature profiles:

```txt
help                 /help
rules_intro          /rules intro copy
rules_acceptance     rules acceptance copy
admin                admin/status copy hooks
fortune              /fortune
welcome              future welcome messages
broadcast_morning    The Vanguard Frequency generation
broadcast_evening    W.W.N. Broadcast generation
```

This keeps Wilhelmina recognizable while allowing each feature to apply the right functional limits. The old umbrella oracle/persona architecture remains removed.

## AI-backed features

`/8ball`, `/fortune`, `/help`, `/rules`, and `/broadcast-admin preview/send-test` can use AI first when `OPENAI_API_KEY` is configured, then fall back to static or stored responses if AI is unavailable.

Automatic Memory Ledger extraction is different: when enabled, it uses the private structured-memory provider path and fails closed if the required private retention configuration is unavailable. It has no static fallback that persists guessed memories.

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=8
AI_MAX_RETRIES=1
```

## Running locally

```bash
python bot.py
```

## Tests and checks

```bash
ruff check .
pytest
```

CI runs the same checks on push and pull request.

## Feature flag policy

Required cogs:

```env
ENABLE_CORE=true
ENABLE_ADMIN=true
```

Optional cogs:

```env
ENABLE_HELP=true
ENABLE_RULES=true
ENABLE_MEMORY_ADMIN=true
ENABLE_MEMORY_EXTRACTION=false
ENABLE_INVITE=false
ENABLE_ROLL=false
ENABLE_EIGHT_BALL=false
ENABLE_FORTUNE=false
ENABLE_BROADCASTS=false
```
