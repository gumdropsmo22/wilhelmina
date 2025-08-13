param(
  [string]$RepoRoot,
  [switch]$IncludeC7,
  [switch]$SkipPush,
  [switch]$StatusOnly
)

$ErrorActionPreference = "Stop"

function Section([string]$t){Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan}
function Ensure-Dir([string]$p){ if ($p -and -not (Test-Path $p)) { New-Item -ItemType Directory -Force $p | Out-Null } }

# ---------- Locate repo root robustly ----------
Section "Locate repo"
$tryPaths = @()

if ($RepoRoot -and (Test-Path $RepoRoot)) { $tryPaths += (Resolve-Path $RepoRoot).Path }
if ($PSScriptRoot) { $tryPaths += $PSScriptRoot }
try { $tryPaths += (Get-Location).Path } catch {}

# add parents up to 6 levels
$expanded = @()
foreach($c in ($tryPaths | Select-Object -Unique)){
  if (-not $c) { continue }
  $d = $c
  for($i=0; $i -lt 6 -and $d; $i++){
    if ($expanded -notcontains $d) { $expanded += $d }
    try { $d = Split-Path -Path $d -Parent } catch { $d = $null }
  }
}

$Repo = $null
foreach($c in $expanded){
  if ($c -and (Test-Path (Join-Path $c ".git"))) { $Repo = $c; break }
}
if (-not $Repo) {
  foreach($c in $expanded){
    if ($c -and (Test-Path $c)) { $Repo = $c; break }
  }
}
if (-not $Repo) { throw "Could not determine repo root from: " + ($expanded -join ", ") }

Write-Host ("Root: {0}" -f $Repo)
Push-Location $Repo

# ---------- Helpers ----------
function Get-ProjectPython {
  $venv = Join-Path $Repo ".venv"
  $py = Join-Path $venv "Scripts\python.exe"
  if (Test-Path $py) { return $py }
  return $null
}

function Read-DotEnv {
  $envPath = Join-Path $Repo ".env"
  $map = @{}
  if (Test-Path $envPath) {
    Get-Content $envPath -Encoding UTF8 | ForEach-Object {
      $line = $_.Trim()
      if (-not $line -or $line.StartsWith("#")) { return }
      $kv = $line -split "=", 2
      if ($kv.Count -eq 2) { $map[$kv[0].Trim()] = $kv[1].Trim() }
    }
  }
  return $map
}

function Ensure-CoreCog {
  $corePath = Join-Path $Repo "cogs\core.py"
  if (-not (Test-Path $corePath)) {
    Ensure-Dir (Split-Path -Parent $corePath)
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
    Set-Content -Path $corePath -Value $core -Encoding UTF8
    Write-Host "Created cogs\core.py"
  } else {
    Write-Host "cogs\core.py already present"
  }
}

function Find-BaseRef {
  git fetch origin | Out-Null
  $cands = git branch -r --list "origin/chore/C3-C5-skeleton*"
  if ($cands) { return ($cands | Select-Object -First 1).ToString().Trim() }
  else { return "origin/main" }
}

function Push-C6 {
  Section "Push C6 - core slash commands"
  Ensure-CoreCog
  $baseRef = Find-BaseRef
  Write-Host "Base: $baseRef" -ForegroundColor DarkGray

  git checkout -B chore-base $baseRef | Out-Null
  git checkout -B feat/C6-core-commands chore-base | Out-Null

  git add -A
  $pending = git status --porcelain
  if ($pending) { git commit -m "feat(core): add /about, /uptime, /sync and dev copy_global_to" | Out-Null }
  try { git push -u origin feat/C6-core-commands } catch {}
}

function Setup-C7 {
  Section "C7 - dev QoL (ruff/black, pre-commit, CI)"
  Ensure-Dir ".github"
  Ensure-Dir ".github\workflows"

$pyproject = @'
[tool.black]
line-length = 100
target-version = ["py312"]

[tool.ruff]
line-length = 100
target-version = "py312"
select = ["E","F","I","B","BLE","UP"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["cogs","config","utils"]
'@
  Set-Content -Path ".\pyproject.toml" -Value $pyproject -Encoding UTF8

$precommit = @'
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.8
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
'@
  Set-Content -Path ".\.pre-commit-config.yaml" -Value $precommit -Encoding UTF8

$ci = @'
name: ci
on:
  push: { branches: ["**"] }
  pull_request:
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Install dev tools
        run: |
          python -m pip install --upgrade pip
          pip install ruff black
      - name: Ruff
        run: ruff check .
      - name: Black
        run: black --check .
'@
  Set-Content -Path ".github\workflows\ci.yml" -Value $ci -Encoding UTF8

  $py = Get-ProjectPython
  if ($py) {
    try { & $py -m pip install -U ruff black pre-commit | Out-Null } catch {}
    try { & $py -m pre_commit install | Out-Null } catch {}
    try { & $py -m ruff check --fix . | Out-Null } catch {}
    try { & $py -m black . | Out-Null } catch {}
  } else {
    Write-Host "Note: .venv Python not found; skipped local lint/format install."
  }

  git add -A
  $pending = git status --porcelain
  if ($pending) {
    git commit -m "chore(dev): add ruff/black, pre-commit, CI; format codebase" | Out-Null
  }
  try { git push -u origin feat/C7-dev-qol } catch {}
}

function Show-WilhelminaStatus {
  Section "Repo & runtime status (Fonzie)"
  try {
    $branch = git branch --show-current
    $remote = git remote -v | Select-String "origin" | Select-Object -First 1
    Write-Host ("Branch: {0}" -f $branch)
    if ($remote) { Write-Host ("Remote: {0}" -f ($remote -replace '\s+fetch.*','')) }
    Write-Host "Recent commits:"; git log --oneline -n 5 --decorate --graph
  } catch { Write-Host "Git info unavailable: $_" -ForegroundColor Yellow }

  $p = Get-ProjectPython
  if ($p) {
    Write-Host "Python:" (& $p -V)
    $dp = & $p -m pip show discord.py | Select-String "^Version:"
    if ($dp) { Write-Host ("discord.py: {0}" -f ($dp.ToString().Split(':')[1].Trim())) }
  } else {
    Write-Host "Python: .venv not found"
  }

  $dotenv = Read-DotEnv
  $gid = if ($dotenv.ContainsKey("DEV_GUILD_ID")) { $dotenv["DEV_GUILD_ID"] } else { "" }
  $tok = if ($dotenv.ContainsKey("DISCORD_TOKEN")) { $dotenv["DISCORD_TOKEN"] } else { $env:DISCORD_TOKEN }
  $envName = if ($dotenv.ContainsKey("APP_ENV")) { $dotenv["APP_ENV"] } else { $env:APP_ENV }
  if ($tok) {
    $masked = if ($tok.Length -ge 8) { $tok.Substring(0,4) + "…" + $tok.Substring($tok.Length-4) } else { "***" }
    Write-Host "Token: present ($masked)"
  } else { Write-Host "Token: MISSING" -ForegroundColor Yellow }
  Write-Host "APP_ENV: $envName"
  Write-Host "DEV_GUILD_ID: $gid"

  try {
    if ($p) {
      $localCmds = & $p -c "import bot; print([c.name for c in bot.bot.tree.get_commands()])"
      Write-Host "Local app commands (code): $localCmds"
    }
  } catch {
    Write-Host "Local command introspection failed: $_" -ForegroundColor Yellow
  }

  if ($tok) {
    try {
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      $h = @{ Authorization = "Bot $tok" }
      $me = Invoke-RestMethod -Method GET -Uri "https://discord.com/api/v10/users/@me" -Headers $h
      $app = Invoke-RestMethod -Method GET -Uri "https://discord.com/api/v10/oauth2/applications/@me" -Headers $h
      Write-Host ("Bot user: {0}#{1} (id {2}); App id: {3}" -f $me.username,$me.discriminator,$me.id,$app.id)
      if ($gid) {
        $url = "https://discord.com/api/v10/applications/$($app.id)/guilds/$gid/commands"
        $cmds = Invoke-RestMethod -Method GET -Uri $url -Headers $h
        $names = ($cmds | ForEach-Object { $_.name }) -join ", "
        Write-Host ("Guild slash-commands ({0}): {1}" -f ($cmds.Count), $names)
      }
    } catch {
      Write-Host "Discord API status check failed: $_" -ForegroundColor Yellow
    }
  }

  $must = @("bot.py","cogs\core.py","config\settings.py",".env")
  $ok = @(); foreach($f in $must){ $ok += ("{0}: {1}" -f $f, (Test-Path (Join-Path $Repo $f))) }
  Write-Host ("Files: " + ($ok -join " | "))
}

# ---------- Main ----------
try {
  if (-not $StatusOnly -and -not $SkipPush) { Push-C6 }
  if ($IncludeC7 -and -not $StatusOnly) { Setup-C7 }
  Show-WilhelminaStatus
} finally {
  Pop-Location
  Section "Done"
  if ($Host.Name -notmatch "Visual Studio Code") { Write-Host "Press any key to continue . . ."; $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") }
}
