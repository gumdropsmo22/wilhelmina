param(
  [string]$RepoRoot = "$HOME\wilhelmina",
  [switch]$KeepHelperFiles
)

$ErrorActionPreference = "Stop"

function Section([string]$t){ Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }

# Try to locate repo
Section "Locate repo"
if (-not (Test-Path $RepoRoot)) {
  # fallback to the folder where this script lives
  $RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
  throw "Could not find a Git repo at: $RepoRoot"
}
Set-Location $RepoRoot
Write-Host "Root: $RepoRoot"

# Start a transcript for debugging
$logDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir ("cleanup_reset_c6_{0}.log" -f $stamp)
try { Start-Transcript -Path $logPath -Force | Out-Null } catch {}

# Reset local branch to match remote feat/C6-core-commands
Section "Reset local to origin/feat/C6-core-commands"
git fetch origin | Out-Null
git checkout -B feat/C6-core-commands origin/feat/C6-core-commands
git reset --hard HEAD
# Keep ignored files like .env; remove other untracked junk
git clean -fd

# Verify cogs/core.py exists on the branch
Section "Verify cogs/core.py"
$core = Join-Path $RepoRoot "cogs\core.py"
if (Test-Path $core) {
  Write-Host "core.py is present."
} else {
  throw "core.py is missing on origin/feat/C6-core-commands — aborting to avoid accidental loss."
}

# Optionally remove helper files
if (-not $KeepHelperFiles) {
  Section "Remove helper files"
  Get-ChildItem -Path $RepoRoot -Filter "Run-Wilhelmina-*.cmd" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
  $maybe = @(
    "wilhelmina_ops.ps1",
    "rebase_and_push_c6.ps1",
    "Run-Rebase-Push-C6-NoExit.cmd"
  )
  foreach ($f in $maybe) {
    $p = Join-Path $RepoRoot $f
    if (Test-Path $p) { Remove-Item -Force -ErrorAction SilentlyContinue $p }
  }
}

# Show quick status
Section "Status"
git status -sb
git log --oneline -n 3

try { Stop-Transcript | Out-Null } catch {}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Read-Host -Prompt "Press Enter to close"