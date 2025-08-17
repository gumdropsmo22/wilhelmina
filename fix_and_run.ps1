# ----- Wilhelmina: fix, verify, run -----
param([string]$DevGuildId="1384553324031770637")

$ErrorActionPreference="Stop"
Set-Location -Path $PSScriptRoot

function Write-Section{param([string]$T) Write-Host ""; Write-Host "=== $T ===" -ForegroundColor Cyan}

# 1) Get token (hidden) and verify with Discord API
Write-Section "Paste bot token"
$sec = Read-Host -Prompt 'Paste your Discord BOT token (hidden)' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try { $Token = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr).Trim() } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }

if (-not $Token) { throw "No token provided." }

Write-Section "Verify token with Discord"
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  $me = Invoke-RestMethod -Method GET -Uri "https://discord.com/api/v10/users/@me" -Headers @{Authorization="Bot $Token"} -ErrorAction Stop
  Write-Host ("Token OK for user: {0}#{1} (id {2})" -f $me.username,$me.discriminator,$me.id) -ForegroundColor Green
} catch {
  Write-Host "❌ Discord rejected the token. Reset your *Bot Token* in Developer Portal → Bot → Reset Token, then rerun this." -ForegroundColor Red
  throw
}

# 2) Ensure venv + deps
Write-Section "Python venv & deps"
$venv = Join-Path $PSScriptRoot ".venv"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) { & python -m venv $venv }
& $py -m pip install -U pip >$null
& $py -m pip install discord.py python-dotenv >$null

# 3) Write/Update .env (persist token) + session env for immediate run
Write-Section ".env setup"
function Upsert-Env { param([string]$Content,[string]$Key,[string]$Value)
  $pat = "^\s*{0}\s*=.*$" -f [regex]::Escape($Key)
  if ($Content -match $pat) {
    return [regex]::Replace($Content,$pat,("$Key=$Value"),[System.Text.RegularExpressions.RegexOptions]::Multiline)
  } else {
    if ($Content.Length -gt 0 -and -not $Content.EndsWith("`n")) { $Content += "`n" }
    return $Content + "$Key=$Value`n"
  }
}
$envPath = Join-Path $PSScriptRoot ".env"
$envContent = if (Test-Path $envPath) { Get-Content $envPath -Raw -Encoding UTF8 } else { "" }
$envContent = Upsert-Env $envContent "DISCORD_TOKEN" $Token
$envContent = Upsert-Env $envContent "DEV_GUILD_ID" $DevGuildId
$envContent = Upsert-Env $envContent "APP_ENV" "development"
Set-Content -Path $envPath -Value $envContent -Encoding UTF8
$env:DISCORD_TOKEN=$Token; $env:DEV_GUILD_ID=$DevGuildId; $env:APP_ENV="development"
Write-Host "Wrote .env (token + DEV_GUILD_ID)."

# 4) Patch bot.py so sync happens after login (idempotent overwrite)
Write-Section "Patch bot.py"
$botPath = Join-Path $PSScriptRoot "bot.py"
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
_synced = False

@bot.event
async def on_ready():
    global _synced
    print(f"Wilhelmina online as {bot.user} (guilds: {len(bot.guilds)})")
    if not _synced:
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
        _synced = True

async def load_cogs():
    try:
        await bot.load_extension("cogs.oracles")
    except Exception as e:
        print(f"Note: could not load cogs.oracles ({e})")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in environment.")
    asyncio.run(main())
"@
if (Test-Path $botPath) { Copy-Item $botPath "$botPath.bak" -Force }
Set-Content -Path $botPath -Value $patched -Encoding UTF8

# 5) Launch
Write-Section "Launch"
& $py $botPath
