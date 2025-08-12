param(
  [string]$DevGuildId = "1384553324031770637",
  [switch]$NoRun
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
function Section([string]$t){Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan}

# --- ensure folders
New-Item -ItemType Directory -Force .\config | Out-Null

# --- ensure .gitignore sane
Section ".gitignore"
$giPath = Join-Path $PSScriptRoot ".gitignore"
$need = @(
  ".env", ".venv/", "__pycache__/", "*.py[cod]", ".pytest_cache/", "archive/node/node_modules/"
)
$gi = if (Test-Path $giPath) { Get-Content $giPath -Raw -Encoding UTF8 } else { "" }
foreach($l in $need){ if ($gi -notmatch [regex]::Escape($l)) { $gi += "$(if($gi -and -not $gi.EndsWith("`n")){"`n"})$l`n" } }
Set-Content -Path $giPath -Value $gi -Encoding UTF8

# --- venv & deps
Section "Python venv & deps"
$venv = Join-Path $PSScriptRoot ".venv"
$py = Join-Path $venv "Scripts\python.exe"
if (!(Test-Path $py)) { & python -m venv $venv }
& $py -m pip install -U pip >$null
& $py -m pip install discord.py python-dotenv >$null

# --- .env upsert helper
function Upsert-EnvLine([string]$content,[string]$key,[string]$value){
  $pat = "^\s*{0}\s*=.*$" -f [regex]::Escape($key)
  if ($content -match $pat) {
    return [regex]::Replace($content,$pat,("$key=$value"),[System.Text.RegularExpressions.RegexOptions]::Multiline)
  } else {
    if ($content.Length -gt 0 -and -not $content.EndsWith("`n")) { $content += "`n" }
    return $content + "$key=$value`n"
  }
}

# --- load/write .env
Section ".env"
$envPath = Join-Path $PSScriptRoot ".env"
$envText = if (Test-Path $envPath) { Get-Content $envPath -Raw -Encoding UTF8 } else { "" }
$envText = Upsert-EnvLine $envText "DEV_GUILD_ID" $DevGuildId
$envText = Upsert-EnvLine $envText "APP_ENV" "development"
$haveToken = ($envText -match "^\s*DISCORD_TOKEN\s*=")
if (-not $haveToken) {
  $sec = Read-Host -Prompt 'Paste your Discord BOT token (hidden)' -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
  try { $tok = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr).Trim() } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  if (-not $tok) { throw "No token provided." }
  $envText = Upsert-EnvLine $envText "DISCORD_TOKEN" $tok
}
Set-Content -Path $envPath -Value $envText -Encoding UTF8

# --- config/settings.py
Section "config/settings.py"
$settings = @"
import os
from pathlib import Path
from dotenv import load_dotenv

# load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

APP_ENV      = os.getenv("APP_ENV", "development")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")
DISCORD_TOKEN= os.getenv("DISCORD_TOKEN")
LOG_LEVEL    = os.getenv("LOG_LEVEL", "INFO")

def require_token() -> str:
    if not DISCORD_TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    return DISCORD_TOKEN
"@
Set-Content -Path .\config\settings.py -Value $settings -Encoding UTF8

# --- bot.py
Section "bot.py"
$botPath = Join-Path $PSScriptRoot "bot.py"
if (Test-Path $botPath) { Copy-Item $botPath "$botPath.bak" -Force }
$bot = @"
import asyncio, logging, sys
import discord
from discord.ext import commands
from discord import app_commands
from config import settings

# logging
level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(stream=sys.stdout, level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("wilhelmina")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
_synced = False

@bot.event
async def on_ready():
    global _synced
    log.info("Online as %s (guilds: %d)", bot.user, len(bot.guilds))
    if not _synced:
        try:
            if settings.APP_ENV == "development" and settings.DEV_GUILD_ID:
                guild = discord.Object(id=int(settings.DEV_GUILD_ID))
                synced = await bot.tree.sync(guild=guild)
                log.info("[DEV] Synced %d commands to guild %s", len(synced), settings.DEV_GUILD_ID)
            else:
                synced = await bot.tree.sync()
                log.info("[GLOBAL] Synced %d commands", len(synced))
        except Exception as e:
            log.exception("Sync failed: %s", e)
        _synced = True

@bot.tree.command(name="ping", description="Health check for Wilhelmina")
async def ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {ms} ms • env={settings.APP_ENV}", ephemeral=True)

async def load_cogs():
    try:
        await bot.load_extension("cogs.oracles")
    except Exception as e:
        log.warning("Could not load cogs.oracles: %s", e)

async def main():
    token = settings.require_token()
    async with bot:
        await load_cogs()
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
"@
Set-Content -Path $botPath -Value $bot -Encoding UTF8

# --- compile quick check
Section "Compile"
& $py -m compileall $PSScriptRoot | Out-Null

# --- pin requirements
Section "requirements.txt"
& $py -m pip freeze | Set-Content -Path (Join-Path $PSScriptRoot "requirements.txt") -Encoding UTF8

# --- git branch/commit/push
Section "Git commit & push"
$branchBase = "chore/C3-C5-skeleton"
$branch = $branchBase
# try to create, if exists, add timestamp
try {
  git checkout -b $branch 2>$null
} catch {
  $branch = "$branchBase-$(Get-Date -Format yyyyMMdd-HHmmss)"
  git checkout -b $branch | Out-Null
}
git add -A
git commit -m "chore: C3–C5 skeleton — settings, logging, /ping, pinned deps" | Out-Null
git push -u origin $branch

# --- run (optional)
if (-not $NoRun) {
  Section "Launch bot (DEV guild $DevGuildId)"
  & $py $botPath
} else {
  Write-Host "Skip run: use  .\.venv\Scripts\python .\bot.py  when ready." -ForegroundColor Yellow
}
