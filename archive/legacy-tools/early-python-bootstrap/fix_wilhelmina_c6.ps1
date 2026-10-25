[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Section { param([string]$t) Write-Host "" ; Write-Host ("=== {0} ===" -f $t) -ForegroundColor Cyan }

# 1) Locate repo root
Section "Locate repo"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = @($here, "$env:USERPROFILE\wilhelmina")
$root = $null
foreach ($c in $candidates) {
  if ((Test-Path $c -PathType Container) -and (Test-Path (Join-Path $c ".git"))) { $root = $c; break }
}
if (-not $root) { throw "Couldn't find repo. Put this file inside your wilhelmina folder." }
Set-Location -Path $root
Write-Host ("Root: {0}" -f $root)

# 2) Ensure cogs/core.py exists (create if missing)
Section "Ensure cogs/core.py"
if (-not (Test-Path ".\cogs" -PathType Container)) { New-Item -ItemType Directory -Path ".\cogs" | Out-Null }

$core = @'
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

$dest = ".\cogs\core.py"
$writeIt = $false
if (-not (Test-Path $dest)) { $writeIt = $true }
else {
  $len = (Get-Item $dest).Length
  if ($len -lt 50) { $writeIt = $true }
}
if ($writeIt) {
  Set-Content -Path $dest -Value $core -Encoding UTF8
  Write-Host "Wrote cogs\core.py"
} else {
  Write-Host "cogs\core.py already looks fine."
}

# 3) Commit/push to feat/C6-core-commands
Section "Git push C6"
git fetch origin | Out-Null
$base = "origin/chore/C3-C5-skeleton-20250812-222751"
$hasBase = (git branch -r --list $base)
if (-not $hasBase) { $base = "origin/main" }
git checkout -B chore-base $base | Out-Null
git checkout -B feat/C6-core-commands chore-base | Out-Null
git add cogs/core.py | Out-Null
$pending = git status --porcelain
if ($pending) {
  git commit -m "feat(core): add /about, /uptime, /sync and dev copy_global_to" | Out-Null
  git push -u origin feat/C6-core-commands | Out-Null
  Write-Host "Pushed branch feat/C6-core-commands to origin."
} else {
  Write-Host "No changes to commit; branch already up-to-date."
}

# 4) Quick status
Section "Status"
Write-Host ("File exists: {0}" -f (Test-Path ".\cogs\core.py"))
git --no-pager log --oneline -n 3 --decorate

Write-Host "`n=== Done ==="
Read-Host "Press Enter to close" | Out-Null
