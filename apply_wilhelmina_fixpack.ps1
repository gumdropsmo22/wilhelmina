# Filename: apply_wilhelmina_fixpack.ps1
# Purpose : Bring the skeleton to a clean, runnable state (C1–C6 prep).
# Usage   : pwsh ./apply_wilhelmina_fixpack.ps1 [-Commit] [-Branch C6-fixpack-20250821]
# Notes   : Idempotent. Creates backups under .\backup\<timestamp>\...

[CmdletBinding()]
param(
  [switch]$Commit,
  [string]$Branch = ("C6-fixpack-" + (Get-Date -Format "yyyyMMdd-HHmm"))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-BackupPath {
  $ts = Get-Date -Format "yyyyMMdd-HHmmss"
  $bp = Join-Path -Path (Get-Location) -ChildPath ("backup\" + $ts)
  New-Item -ItemType Directory -Force -Path $bp | Out-Null
  return $bp
}

function Backup-File {
  param([string]$Path, [string]$BackupRoot)
  if (Test-Path $Path) {
    $dst = Join-Path $BackupRoot $Path
    $dir = Split-Path $dst -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Copy-Item -LiteralPath $Path -Destination $dst -Force
  }
}

function Ensure-Directory {
  param([string]$Path)
  if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Force -Path $Path | Out-Null }
}

function Write-CanonicalFile {
  param([string]$Path, [string]$Content, [string]$BackupRoot)
  Backup-File -Path $Path -BackupRoot $BackupRoot
  $dir = Split-Path $Path -Parent
  if ($dir) { Ensure-Directory $dir }
  # Normalize LF endings for code files
  $Content -replace "`r`n","`n" | Set-Content -LiteralPath $Path -NoNewline -Encoding UTF8
}

function Ensure-LinePresent {
  param([string]$Path, [string[]]$Lines, [string]$BackupRoot)
  if (-not (Test-Path $Path)) {
    Backup-File -Path $Path -BackupRoot $BackupRoot
    $Lines | Set-Content -LiteralPath $Path -Encoding UTF8
    return
  }
  $orig = Get-Content -LiteralPath $Path -Raw
  $set  = ($orig -split "`r?`n")
  $changed = $false
  foreach ($line in $Lines) {
    if ($set -notcontains $line) {
      $set += $line
      $changed = $true
    }
  }
  if ($changed) {
    Backup-File -Path $Path -BackupRoot $BackupRoot
    ($set -join "`n") | Set-Content -LiteralPath $Path -NoNewline -Encoding UTF8
  }
}

function Ensure-ImportRandom {
  param([string]$Path, [string]$BackupRoot)
  if (-not (Test-Path $Path)) { return $false }
  $txt = Get-Content -LiteralPath $Path -Raw
  if ($txt -notmatch '^\s*import\s+random\b') {
    Backup-File -Path $Path -BackupRoot $BackupRoot
    $updated = "import random`n$txt"
    $updated | Set-Content -LiteralPath $Path -NoNewline -Encoding UTF8
    return $true
  }
  return $false
}

function Remove-BOM {
  param([string]$Path, [string]$BackupRoot)
  if (-not (Test-Path $Path)) { return }
  $bytes = [System.IO.File]::ReadAllBytes($Path)
  if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    Backup-File -Path $Path -BackupRoot $BackupRoot
    [System.IO.File]::WriteAllBytes($Path, $bytes[3..($bytes.Length-1)])
  }
}

$backupRoot = New-BackupPath
Write-Host "Backup folder: $backupRoot" -ForegroundColor Cyan

# --- Canonical file contents ---

$bot_py = @'
import os
import logging
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from config.settings import APP_ENV, DEV_GUILD_ID, require_token

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

intents = discord.Intents.default()
intents.message_content = False

class WilBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.start_time = discord.utils.utcnow()

    async def setup_hook(self):
        for ext in ("cogs.core", "cogs.invite", "cogs.errors"):
            try:
                await self.load_extension(ext)
                logging.getLogger("loader").info("Loaded %s", ext)
            except Exception:
                logging.getLogger("loader").exception("Failed to load %s", ext)

        # Dev guild sync on startup for fast iteration
        if APP_ENV == "development" and DEV_GUILD_ID:
            try:
                guild = discord.Object(id=int(DEV_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logging.info("[DEV] Synced %d commands to guild %s", len(synced), DEV_GUILD_ID)
            except Exception:
                logging.getLogger("sync").exception("Dev guild sync failed")

    async def on_ready(self):
        logging.info("Logged in as %s (%s) · APP_ENV=%s", self.user, self.user.id, APP_ENV)

bot = WilBot()

async def _main():
    await bot.start(require_token())

if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logging.info("Shutting down...")
'@

$cogs_core_py = @'
import platform
import time
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import APP_ENV, DEV_GUILD_ID

def _embed(title: str, description: str) -> discord.Embed:
    try:
        from utils import embeds as _emb
        return _emb.system_embed(header=title, description=description)
    except Exception:
        e = discord.Embed(title=title, description=description, color=0x6E00FF)
        return e

class Core(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Latency check")
    async def ping(self, interaction: discord.Interaction):
        ws = self.bot.latency * 1000 if self.bot.latency is not None else 0
        msg = f"websocket ≈ {ws:.0f} ms · env={APP_ENV}"
        await interaction.response.send_message(embed=_embed("▒▒ PING ▒▒", msg), ephemeral=True)

    @app_commands.command(name="about", description="About this bot")
    async def about(self, interaction: discord.Interaction):
        py = platform.python_version()
        dpy = discord.__version__
        msg = f"Python {py} · discord.py {dpy} · env={APP_ENV}"
        await interaction.response.send_message(embed=_embed("▒▒ ABOUT ▒▒", msg), ephemeral=True)

    @app_commands.command(name="uptime", description="How long since last start")
    async def uptime(self, interaction: discord.Interaction):
        now = discord.utils.utcnow()
        delta = now - getattr(self.bot, "start_time", now)
        msg = f"{delta}"
        await interaction.response.send_message(embed=_embed("▒▒ UPTIME ▒▒", msg), ephemeral=True)

    @app_commands.command(name="sync", description="Developer: sync commands to dev guild")
    async def sync(self, interaction: discord.Interaction):
        if APP_ENV != "development" or not DEV_GUILD_ID:
            await interaction.response.send_message(embed=_embed("Sync", "Not in development or DEV_GUILD_ID not set."), ephemeral=True)
            return
        guild = discord.Object(id=int(DEV_GUILD_ID))
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)
        await interaction.response.send_message(embed=_embed("Sync", f"Synced {len(synced)} commands to guild {DEV_GUILD_ID}"), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
'@

$cogs_invite_py = @'
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import APP_ENV

def _embed(title: str, description: str) -> discord.Embed:
    try:
        from utils import embeds as _emb
        return _emb.system_embed(header=title, description=description)
    except Exception:
        return discord.Embed(title=title, description=description, color=0x6E00FF)

def _invite_url(app_id: int, is_dev: bool) -> str:
    perms = 8 if is_dev else 275146426880  # dev=Admin, prod=minimal sensible set
    scopes = "bot%20applications.commands"
    return f"https://discord.com/api/oauth2/authorize?client_id={app_id}&permissions={perms}&scope={scopes}"

class Invite(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="invite", description="Get the bot invite link")
    async def invite(self, interaction: discord.Interaction):
        app = (self.bot.application or await self.bot.application_info())
        url = _invite_url(app.id, APP_ENV == "development")
        await interaction.response.send_message(embed=_embed("Invite", f"[Add me to a server]({url})"), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Invite(bot))
'@

$cogs_errors_py = @'
import traceback
import discord
from discord.ext import commands
from discord import app_commands

def _embed(title: str, description: str) -> discord.Embed:
    try:
        from utils import embeds as _emb
        return _emb.system_embed(header=title, description=description)
    except Exception:
        return discord.Embed(title=title, description=description, color=0x6E00FF)

class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Classify a few common cases, keep copy terse
        if isinstance(error, app_commands.MissingPermissions):
            msg = "You lack the required permissions."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"On cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, app_commands.CheckFailure):
            msg = "You cannot use this command."
        else:
            msg = "Something cracked in the mirror. The action failed."
        try:
            await interaction.response.send_message(embed=_embed("Error", msg), ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=_embed("Error", msg), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
'@

$config_settings_py = @'
import os
from pathlib import Path
from dotenv import load_dotenv

# Load ../.env
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

APP_ENV       = os.getenv("APP_ENV", "development")
DEV_GUILD_ID  = os.getenv("DEV_GUILD_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_LEVEL     = os.getenv("LOG_LEVEL", "INFO")

def require_token() -> str:
    if not DISCORD_TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    return DISCORD_TOKEN
'@

$persona_py = @'
# Persona utilities with optional OpenAI wiring. Safe if OPENAI is absent.
from typing import Optional

_client = None
try:
    from openai import OpenAI  # optional
    _client = OpenAI()
except Exception:
    _client = None

def fortune_line(prompt: str) -> Optional[str]:
    # In skeleton phase, return None to allow cog fallback text
    if not _client:
        return None
    # Placeholder for future: call your chosen model; keep None fallback now
    return None
'@

$env_example = @'
# Discord
DISCORD_TOKEN=
CLIENT_ID=
DEV_GUILD_ID=

# Environment
APP_ENV=development
LOG_LEVEL=INFO

# Optional APIs (future)
# OPENAI_API_KEY=
# WEATHER_API_KEY=
# NEWS_API_KEY=
# ASTRO_API_KEY=
# TZ_API_KEY=
'@

$gitignore_lines = @'
# Environment
.env

# Python
.venv/
__pycache__/
*.py[cod]
.pytest_cache/

# Archives
*.bundle
*.tar
*.tar.gz
'@ -split "`r?`n"

# --- Apply canonical writes/patches ---

Write-CanonicalFile -Path "bot.py" -Content $bot_py -BackupRoot $backupRoot
Write-CanonicalFile -Path "cogs/core.py" -Content $cogs_core_py -BackupRoot $backupRoot
Write-CanonicalFile -Path "cogs/invite.py" -Content $cogs_invite_py -BackupRoot $backupRoot
Write-CanonicalFile -Path "cogs/errors.py" -Content $cogs_errors_py -BackupRoot $backupRoot
Write-CanonicalFile -Path "config/settings.py" -Content $config_settings_py -BackupRoot $backupRoot
Write-CanonicalFile -Path "utils/persona.py" -Content $persona_py -BackupRoot $backupRoot

# Ensure utils/embeds.py exists and imports random
if (-not (Test-Path "utils")) { New-Item -ItemType Directory -Force -Path "utils" | Out-Null }
if (-not (Test-Path "utils/embeds.py")) {
  $minimal_embeds = @'
import random
import discord

def system_embed(header: str, description: str) -> discord.Embed:
    e = discord.Embed(title=header, description=description, color=0x6E00FF)
    return e
'@
  Write-CanonicalFile -Path "utils/embeds.py" -Content $minimal_embeds -BackupRoot $backupRoot
} else {
  Ensure-ImportRandom -Path "utils/embeds.py" -BackupRoot $backupRoot | Out-Null
}

# Normalize .env.example
Write-CanonicalFile -Path ".env.example" -Content $env_example -BackupRoot $backupRoot

# Patch .gitignore with required lines
Ensure-LinePresent -Path ".gitignore" -Lines $gitignore_lines -BackupRoot $backupRoot

# Remove BOM from config/settings.py (if any)
Remove-BOM -Path "config/settings.py" -BackupRoot $backupRoot

# Leave requirements.txt alone; openai is optional now due to guarded import.

# --- Optional Git branch and commit ---
if ($Commit) {
  try {
    git rev-parse --is-inside-work-tree *> $null 2>&1
    $inside = $LASTEXITCODE -eq 0
  } catch { $inside = $false }
  if ($inside) {
    git checkout -b $Branch 2>$null | Out-Null
    git add .
    git commit -m "C6 fixpack: logging, dev sync, core/ invite/ errors cogs, persona guard, embeds import, env/gitignore normalization" | Out-Null
    Write-Host "Committed on branch $Branch" -ForegroundColor Green
  } else {
    Write-Host "Not a git repo. Skipping commit." -ForegroundColor Yellow
  }
}

Write-Host "Fixpack complete. Start with:  python bot.py" -ForegroundColor Green
'@

# ---------------- End of script ----------------
