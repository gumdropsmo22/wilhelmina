# Wilhelmina Bot

Wilhelmina is a Python Discord bot built with `discord.py` for a dedicated home server. The project is moving toward modular onboarding, AI-backed interactions, administrative tools, scheduled messaging, and server community workflows.

## Runtime model

Wilhelmina is configured for a **brand-new dedicated Discord server**.

Existing-server takeover, channel archival, and automatic server transformation are not supported runtime modes. The bot should be invited into its home guild, configured with `HOME_GUILD_ID`, and expanded through feature-flagged cogs.

## Feature architecture

Features are independent modules. There is no umbrella `oracles` cog in the active runtime.

Current cogs:

```txt
cogs.core          /about, /uptime
cogs.admin         /admin diagnostics, /admin features, /admin sync, /admin config ...
cogs.help          /help
cogs.rules         /rules, /rules-admin ...
cogs.invite        /invite
cogs.roll          /roll
cogs.eight_ball    /8ball
cogs.fortune       /fortune
```

Each optional feature has its own flag:

```env
ENABLE_HELP=true
ENABLE_RULES=true
ENABLE_INVITE=false
ENABLE_ROLL=false
ENABLE_EIGHT_BALL=false
ENABLE_FORTUNE=false
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
```

`DEV_GUILD_ID` is accepted as a legacy alias for `HOME_GUILD_ID`, but new setups should use `HOME_GUILD_ID`.

## SQLite persistence

Wilhelmina stores dedicated-server configuration, administrative audit events, onboarding state, rules versions, and rules acceptance records in SQLite.

```env
DATABASE_PATH=data/wilhelmina.sqlite3
```

Relative paths resolve from the repository root. The SQLite file is local runtime state and should be backed up before deployment moves, schema changes, or manual database edits.

Current persistence stores:

```txt
guild_config
audit_log
onboarding_state
rules_versions
rules_acceptance
schema_migrations
```

The stored guild configuration is the source of truth for server role/channel IDs after Phase 2. Environment variables for role/channel IDs are not used by the new config layer.

## Living Command Grimoire

`/help` opens Wilhelmina's dynamic public command grimoire. It reads the live slash-command tree, hides admin tooling, groups public commands into categories, and can show sealed future doors such as tarot, readings, rituals, welcome, and broadcast.

The grimoire uses the Persona Engine's `guide` voice channel for short AI-polished intro text when `OPENAI_API_KEY` is configured. If AI is unavailable, it falls back to deterministic copy.

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

## Persona Engine

Wilhelmina now has a central Persona Engine with one base voice and feature-specific voice channels.

Current voice channels:

```txt
guide           /help
ritual          /rules and rules acceptance
oracle          /fortune
administrative  admin/status copy hooks
welcome         future welcome messages
```

This keeps Wilhelmina recognizable while allowing each feature to speak through the right channel. The old umbrella oracle/persona architecture remains removed.

## AI-backed features

`/8ball`, `/fortune`, `/help`, and `/rules` can use AI first when `OPENAI_API_KEY` is configured, then fall back to static or stored responses if AI is unavailable.

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
ENABLE_INVITE=false
ENABLE_ROLL=false
ENABLE_EIGHT_BALL=false
ENABLE_FORTUNE=false
```

Required cogs fail startup when broken. Optional cogs are logged and skipped so unfinished features do not take down the runtime.
