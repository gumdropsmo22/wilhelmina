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
cogs.welcome            automatic configured-channel join greeting
cogs.memory_admin       /memory-admin ...
cogs.memory_extraction  interaction-scoped automatic Memory Ledger extraction
cogs.chat               memory-aware direct-interaction chat with bounded local continuity
cogs.invite             /invite
cogs.roll               /roll
cogs.eight_ball         /8ball
cogs.fortune            /fortune
cogs.broadcasts         /broadcast-admin ...
```

Phase-5 context intelligence lives in `services.memory_context`. Phase 6 adds `services.chat` for deterministic routing/audience authorization, `services.chat_response` for the private provider-backed Wilhelmina response path, `services.chat_continuity` for bounded in-process recent conversation state, and `cogs.chat` for Discord event adaptation. The model never becomes the authority for memory reveal scope or member identity.

Each optional feature has its own flag:

```env
ENABLE_HELP=true
ENABLE_RULES=true
ENABLE_WELCOME=false
ENABLE_MEMORY_ADMIN=true
ENABLE_MEMORY_EXTRACTION=false
ENABLE_CHAT=false
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

Phase 6 adds **no chat transcript table**. Its recent conversation history, duplicate-message state, conversation locks, and provider-concurrency state exist only in process memory and reset on bot restart. The Memory Ledger remains the durable long-term memory system.

Private identity schema v12 stores preferred name, full canonical birth date, and timestamps; current Discord display name remains in the Coven Registry. The obsolete adult-memory-consent timestamp/version columns are physically removed. The existing under-18 profile-completion behavior remains unchanged and is a separate product decision.

The stored guild configuration is the source of truth for server role/channel IDs after Phase 2. Environment variables for role/channel IDs are not used by the new config layer.

## Living Command Grimoire

`/help` opens Wilhelmina's dynamic public command grimoire. It reads the live slash-command tree, hides admin tooling, groups public commands into categories, and can show sealed future doors such as tarot, readings, rituals, and broadcast.

Welcome is not a slash command. When `ENABLE_WELCOME=true`, a human joining `HOME_GUILD_ID` receives one Wilhelmina-styled greeting in the configured `welcome_channel_id`. The feature is disabled by default until final rollout and live validation.

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
