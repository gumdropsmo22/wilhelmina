# Wilhelmina DEV launcher (test guild)
[CmdletBinding()]
param(
  [string]$DevGuildId = "1384553324031770637",
  [string]$Token,
  [switch]$PersistToken,
  [switch]$NoPatchBot
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Section { param([string]$Title) Write-Host ""; Write-Host "=== $Title ===" -ForegroundColor Cyan }

function Upsert-EnvKey {
  param([string]$Content,[string]$Key,[string]$Value)
  $pattern = "^\s*{0}\s*=.*$" -f [regex]::Escape($Key)
  if ($Content -match $pattern) {
    return [regex]::Replace($Content,$pattern,("{0}={1}" -f $Key,$Value),[System.Text.RegularExpressions.RegexOptions]::Multiline)
  } else {
    if ($Content.Length -gt 0 -and -not $Content.EndsWith("`n")) { $Content += "`n" }
    return $Content + ("{0}={1}`n" -f $Key,$Value)
  }
}

Write-Section "Env file (.env)"
$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
  $template = @"
DISCORD_TOKEN=
DEV_GUILD_ID=$DevGuildId
APP_ENV=development
"@
  Set-Content -Path $envPath -Value $template -Encoding UTF8
  Write-Host "Created .env with DEV_GUILD_ID=$DevGuildId and APP_ENV=development"
} else {
  $envContent = Get-Content -Path $envPath -Raw -Encoding UTF8
  $envContent = Upsert-EnvKey -Content $envContent -Key "DEV_GUILD_ID" -Value $DevGuildId
  $envContent = Upsert-EnvKey -Content $envContent -Key "APP_ENV" -Value "development"
  if ($PersistToken.IsPresent -and $Token) { $envContent = Upsert-EnvKey -Content $envContent -Key "DISCORD_TOKEN" -Value $Token }
  Set-Content -Path $envPath -Value $envContent -Encoding UTF8
  Write-Host "Updated .env with DEV_GUILD_ID=$DevGuildId and APP_ENV=development"
}

# Session env so it works immediately
$env:DEV_GUILD_ID = $DevGuildId
$env:APP_ENV = "development"
if ($Token -and -not $PersistToken.IsPresent) { $env:DISCORD_TOKEN = $Token; Write-Host "DISCORD_TOKEN set for this session only." }

Write-Section "Python venv"
$venvDir = Join-Path $PSScriptRoot ".venv"; $venvPy = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Host "Creating virtual environment (.venv)…"; & python -m venv $venvDir } else { Write-Host "Virtual environment already exists." }

Write-Section "Python deps"
& $venvPy -m pip install -U pip
& $venvPy -m pip install discord.py python-dotenv

Write-Section "bot.py patch (idempotent)"
$botPath = Join-Path $PSScriptRoot "bot.py"; $needsPatch = $true
if (Test-Path $botPath) {
  $botContent = Get-Content -Path $botPath -Raw -Encoding UTF8
  if ($botContent -match "from dotenv import load_dotenv") { $needsPatch = $false; Write-Host "bot.py already loads dotenv; skipping patch. (Use -NoPatchBot to force skip)" }
}
if (-not $NoPatchBot.IsPresent -and $needsPatch) {
  if (Test-Path $botPath) { Copy-Item $botPath "$botPath.bak" -Force; Write-Host "Backed up bot.py to bot.py.bak" }
$patched = @"
import os, asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV","development")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Wilhelmina online as {bot.user} (guilds: {len(bot.guilds)})")

async def sync_commands():
    try:
        if APP_ENV == "development" and DEV_GUILD_ID:
            guild = discord.Object(id=int(DEV_GUILD_ID))
            synced = await bot.tree.sync(guild=guild)
            print(f"[DEV] Synced {len(synced)} commands to guild {DEV_GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            print(f"[GLOBAL] Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync failed: {e}")

async def load_cogs():
    try:
        await bot.load_extension("cogs.oracles")
    except Exception as e:
        print(f"Note: could not load cogs.oracles ({e})")

async def main():
    async with bot:
        await load_cogs()
        await sync_commands()
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in environment.")
    asyncio.run(main())
"@
  Set-Content -Path $botPath -Value $patched -Encoding UTF8
  Write-Host "Patched bot.py to load .env and sync to DEV guild."
}

Write-Section "Compile"
& $venvPy -m compileall $PSScriptRoot

Write-Section "Launch"
Write-Host "Launching Wilhelmina in DEV mode against guild $DevGuildId …"
& $venvPy $botPath
