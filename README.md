# Wilhelmina Bot

Wilhelmina is a Python Discord bot built with `discord.py` for a dedicated home server. The project is moving toward modular onboarding, AI-backed interactions, administrative tools, scheduled messaging, and server community workflows.

## Runtime model

Wilhelmina is intentionally configured for a **brand-new dedicated server**.

Existing-server takeover, channel archival, and automatic server transformation are not supported runtime modes. The bot should be invited into its home guild, configured with `HOME_GUILD_ID`, and expanded through feature-flagged cogs.

## Current commands

Always-on core/admin commands:

```txt
/about
/uptime
/admin diagnostics
/admin features
/admin sync
```

Optional cogs can be enabled with feature flags:

```txt
/invite
/roll
/8ball
/fortune
```

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
python -m pip install -e ".[dev,oracles]"
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
ENABLE_CORE=true
ENABLE_ADMIN=true
```

`DEV_GUILD_ID` is still accepted as a legacy alias for `HOME_GUILD_ID`, but new setups should use `HOME_GUILD_ID`.

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
ENABLE_INVITE=false
ENABLE_ORACLES=false
```

Required cogs fail startup when broken. Optional cogs are logged and skipped so unfinished features do not take down the runtime.

## License

MIT © 2025
