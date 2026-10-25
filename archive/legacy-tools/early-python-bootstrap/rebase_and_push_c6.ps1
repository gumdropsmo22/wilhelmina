param(
  [switch]$PauseAtEnd,
  [switch]$Log
)

$ErrorActionPreference = "Stop"

function Section([string]$t){ Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }

function Find-RepoRoot {
  $candidates = @()
  if ($PSScriptRoot) { $candidates += $PSScriptRoot }
  if ($HOME) { $candidates += (Join-Path $HOME "wilhelmina") }
  $candidates += (Get-Location).Path
  $seen = @{}
  foreach ($c in $candidates) {
    if (-not $c -or $seen.ContainsKey($c)) { continue }
    $seen[$c] = $true
    try {
      if (Test-Path (Join-Path $c ".git") -PathType Container -ErrorAction SilentlyContinue -and
          Test-Path (Join-Path $c "bot.py") -ErrorAction SilentlyContinue) { return $c }
    } catch {}
  }
  throw "Could not locate repo root (needs .git and bot.py)."
}

function Ensure-CoreFile($root) {
  $core = Join-Path $root "cogs\core.py"
  if (Test-Path $core) {
    Write-Host "cogs\core.py already present"
    return
  }
  Section "Ensure cogs/core.py"
  $dir = Split-Path $core -Parent
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  $content = @'
import os, time, platform
import discord
from discord import app_commands
from discord.ext import commands

class Core(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="about", description="About this bot")
    async def about(self, interaction: discord.Interaction):
        msg = (
            f"**Wilhelmina** skeleton is alive."
            f" Python {platform.python_version()} • discord.py {discord.__version__}"
            f" • env={os.getenv('APP_ENV','development')}"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="uptime", description="Show bot uptime")
    async def uptime(self, interaction: discord.Interaction):
        started = getattr(self.bot, "start_ts", time.time())
        secs = int(time.time() - started)
        h, r = divmod(secs, 3600); m, s = divmod(r, 60)
        await interaction.response.send_message(f"Uptime: {h}h {m}m {s}s", ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="sync", description="Admin: resync slash commands")
    async def sync(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Admins only.", ephemeral=True)
        dev = os.getenv("APP_ENV","development") == "development"
        gid = os.getenv("DEV_GUILD_ID")
        if dev and gid:
            guild = discord.Object(id=int(gid))
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            return await interaction.response.send_message(f"Synced {len(synced)} cmds to dev guild.", ephemeral=True)
        synced = await self.bot.tree.sync()
        await interaction.response.send_message(f"Synced {len(synced)} cmds globally.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
'@
  Set-Content -Path $core -Value $content -Encoding UTF8
  Write-Host "Wrote cogs\core.py"
}

# Main
try {
  Section "Locate repo"
  $root = Find-RepoRoot
  Write-Host ("Root: {0}" -f $root)

  if ($Log) {
    $logs = Join-Path $root "logs"
    if (!(Test-Path $logs)) { New-Item -ItemType Directory -Force $logs | Out-Null }
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $logPath = Join-Path $logs ("rebase_push_c6_{0}.log" -f $stamp)
    Start-Transcript -Path $logPath -Append | Out-Null
    Write-Host ("Logging to {0}" -f $logPath)
  }

  Ensure-CoreFile -root $root

  Section "Git rebase + push C6"
  & git -C $root fetch origin | Out-Null

  # Ensure we have a local branch tracking remote if it exists
  $hasLocal = (& git -C $root rev-parse --verify feat/C6-core-commands 2>$null) -ne $null
  if (-not $hasLocal) {
    $hasRemote = (& git -C $root ls-remote --heads origin feat/C6-core-commands) -ne $null
    if ($hasRemote) {
      & git -C $root checkout -b feat/C6-core-commands origin/feat/C6-core-commands | Out-Null
    } else {
      & git -C $root checkout -b feat/C6-core-commands | Out-Null
    }
  } else {
    & git -C $root checkout feat/C6-core-commands | Out-Null
  }

  # Pull with rebase
  try {
    & git -C $root pull --rebase origin feat/C6-core-commands
  } catch {
    Write-Host "Rebase pull reported an issue; showing status:" -ForegroundColor Yellow
    & git -C $root status -sb
    throw
  }

  # Stage & commit if needed
  & git -C $root add -A
  $pending = & git -C $root status --porcelain
  if ($pending) {
    & git -C $root commit -m "feat(core): add /about, /uptime, /sync and dev copy_global_to" | Out-Null
  }

  # Push
  & git -C $root push origin feat/C6-core-commands

  Section "Status"
  & git -C $root log --oneline -n 3 --decorate
  $aheadBehind = & git -C $root rev-list --left-right --count origin/feat/C6-core-commands...feat/C6-core-commands 2>$null
  if ($aheadBehind) {
    $parts = $aheadBehind -split "\s+"
    Write-Host ("Behind {0}, Ahead {1}" -f $parts[0], $parts[1])
  }

} catch {
  Write-Host ("ERROR: {0}" -f $_) -ForegroundColor Red
} finally {
  if ($Log) {
    try { Stop-Transcript | Out-Null } catch {}
  }
  if ($PauseAtEnd) {
    Write-Host ""
    Write-Host "=== Done ==="
    Read-Host "Press Enter to close"
  }
}
