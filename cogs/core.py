
$ErrorActionPreference = "Stop"

function Section([string]$t){Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan}

# Find repo root (walk up until .git)
function Find-RepoRoot([string]$start){
  $d = Resolve-Path -LiteralPath $start
  while ($d -and -not (Test-Path (Join-Path $d ".git"))) {
    $parent = Split-Path $d -Parent
    if ($parent -eq $d) { break }
    $d = $parent
  }
  return $d
}

# Start in script directory but allow being run from subfolders
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Find-RepoRoot $here
if (-not $repo) { throw "Couldn't find a Git repo from $here" }
Set-Location -Path $repo
Section "Locate repo"
Write-Host "Root: $repo"

git fetch origin | Out-Null

$target = "feat/C6-core-commands"
# switch to target branch (create from skeleton base if missing)
if (git branch --list $target) {
  git checkout $target | Out-Null
} else {
  git checkout -B $target origin/chore/C3-C5-skeleton-20250812-222751 | Out-Null
}

Section "Restore cogs/core.py"
if (-not (Test-Path ".\cogs\core.py")) {
  git checkout origin/chore/C3-C5-skeleton-20250812-222751 -- cogs/core.py
  if (-not (Test-Path ".\cogs\core.py")) { throw "Still missing cogs/core.py after checkout." }
} else {
  Write-Host "cogs/core.py already present"
}

Section "Ensure bot loads core"
$botPath = Join-Path $repo "bot.py"
$botText = Get-Content $botPath -Raw -Encoding UTF8
if ($botText -notmatch 'await\s+bot\.load_extension\("cogs\.core"\)') {
  # Try to inject into load_cogs() if present, else append a minimal loader
  if ($botText -match 'async\s+def\s+load_cogs\(\):') {
    $patched = [regex]::Replace($botText,
      'async\s+def\s+load_cogs\(\):\s*\r?\n',
      "async def load_cogs():`r`n    await bot.load_extension(""cogs.core"")`r`n")
    Set-Content -Path $botPath -Value $patched -Encoding UTF8
  } else {
    Add-Content -Path $botPath -Value "`r`nasync def load_cogs():`r`n    await bot.load_extension(""cogs.core"")`r`n" -Encoding UTF8
  }
  git add $botPath
}

git add cogs/core.py
$pending = git status --porcelain
if ($pending) {
  git commit -m "feat(core): restore core cog and ensure bot loads it" | Out-Null
  git push -u origin $target
  Write-Host "Pushed fixes to $target."
} else {
  Write-Host "Nothing to commit."
}

Section "Verify"
Write-Host ("Files: core:{0} | bot:{1}" -f (Test-Path ".\cogs\core.py"), (Test-Path $botPath))
Write-Host "Done."
Read-Host "Press Enter to exit" | Out-Null
