<#  Setup-Wilhelmina.ps1
    One-shot repo cleanup + language engine + oracles update.
    Usage (from repo root):
      powershell -ExecutionPolicy Bypass -File .\Setup-Wilhelmina.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Git($args) {
  & git @args 2>$null
}

Write-Host "==> Checking Git repository..."
$inRepo = $false
try {
  $status = Invoke-Git @("rev-parse","--is-inside-work-tree")
  if ($LASTEXITCODE -eq 0 -and $status -match "true") { $inRepo = $true }
} catch { $inRepo = $false }

if (-not $inRepo) {
  Write-Host "==> Not a Git repo. Initializing..."
  Invoke-Git @("init")
  Invoke-Git @("add",".")
  Invoke-Git @("commit","-m","chore: init repository") | Out-Null
}

# Create working branch (or checkout if exists)
$branch = "refactor/language-engine-oracles"
Write-Host "==> Creating/checking out branch $branch ..."
Invoke-Git @("checkout","-B",$branch) | Out-Null

# Remove vendored venv
Write-Host "==> Removing vendored .venv from Git and disk (if present)..."
Invoke-Git @("rm","-r","--cached",".venv") | Out-Null
if (Test-Path .\.venv) { Remove-Item .\.venv -Recurse -Force }

# Move any archived Node experiment to /attic
if (Test-Path .\archive\node) {
  Write-Host "==> Archiving Node experiment to .\attic\node ..."
  New-Item -ItemType Directory -Path .\attic -Force | Out-Null
  # Prefer git mv; fall back to Move-Item if needed
  Invoke-Git @("mv",".\archive\node",".\attic\node") | Out-Null
  if ($LASTEXITCODE -ne 0) { Move-Item .\archive\node .\attic\node -Force }
}

# Make directories
Write-Host "==> Scaffolding directories ..."
$dirs = @(
  "wilhelmina","wilhelmina\bot","wilhelmina\cogs","wilhelmina\services","wilhelmina\utils","wilhelmina\data",
  "tests"
)
$dirs | ForEach-Object { New-Item -ItemType Directory -Path $_ -Force | Out-Null }

# __init__.py files for packages
@(
  "wilhelmina\__init__.py",
  "wilhelmina\bot\__init__.py",
  "wilhelmina\cogs\__init__.py",
  "wilhelmina\services\__init__.py",
  "wilhelmina\utils\__init__.py"
) | ForEach-Object { if (-not (Test-Path $_)) { Set-Content -Path $_ -Value "" -Encoding UTF8 } }

# .gitignore
@"
.venv/
__pycache__/
*.pyc
.env
.DS_Store
attic/**/.env
"@ | Set-Content -Path .gitignore -Encoding UTF8

# pyproject.toml
@'
[project]
name = "wilhelmina"
version = "0.1.0"
requires-python = ">=3.11"

[tool.ruff]
line-length = 100
target-version = "py311"
fix = true
select = ["E","F","I","UP","B"]
ignore = ["E501"]

[tool.pytest.ini_options]
pythonpath = ["."]
addopts = "-q"

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
strict_optional = false
'@ | Set-Content -Path .\pyproject.toml -Encoding UTF8

# Language Engine
@'
from __future__ import annotations
import asyncio
from typing import Any, Dict, Literal, Optional
from openai import AsyncOpenAI

Place = Literal["embed", "chat"]
Intent = Literal[
    "roll-line", "8ball-line", "misfortune-cookie",
    "cta-share", "morning-broadcast-bit", "generic"
]

class LanguageEngine:
    def __init__(self, model: str, timeout_s: float = 6.0):
        self.client = AsyncOpenAI()
        self.model = model
        self.timeout_s = timeout_s

    def _system_prompt(self, place: Place) -> str:
        return (
            "You are Wilhelmina, a cyber-occult witch DJ. "
            "Voice: haunted glitch, sharp and theatrical, PG-13, concise. "
            "If output is for an embed, keep to 1–2 sentences."
        )

    def _user_prompt(self, intent: Intent, variables: Dict[str, Any]) -> str:
        if intent == "roll-line":
            return (
                "Write one punchy line reacting to a dice roll.\n"
                f"Dice: d{variables['sides']}. Result: {variables['result']}."
                " Avoid numbers beyond the given result; be playful ominous."
            )
        if intent == "8ball-line":
            return (
                "Write a classic Magic 8-Ball style answer in Wilhelmina's voice.\n"
                f"Verdict: {variables['verdict']} (Affirmative/Vague/Negative). "
                f"Question: {variables.get('question','')}\n"
                "Keep it to one short sentence."
            )
        if intent == "misfortune-cookie":
            return (
                "Write a cryptic fortune as if cracked from a cursed cookie. "
                "No categories; just one eerie line. Keep to one sentence."
            )
        if intent == "cta-share":
            return "Write one-sentence CTA to share the server when voice is lively."
        if intent == "morning-broadcast-bit":
            return "Write a short omen or sting for the morning broadcast."
        return variables.get("prompt", "Say one short on-brand line.")

    async def compose(
        self,
        *,
        place: Place,
        intent: Intent,
        variables: Dict[str, Any],
        fallback: Optional[str] = None,
        temperature: float = 0.9,
        max_tokens: int = 80,
    ) -> str:
        try:
            resp = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._system_prompt(place)},
                        {"role": "user", "content": self._user_prompt(intent, variables)},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self.timeout_s,
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or (fallback or "The static withholds its secrets.")
        except Exception:
            return fallback or "The signal stutters—try again soon."

_engine_singleton: Optional[LanguageEngine] = None

def get_engine(model_env: Optional[str] = None) -> LanguageEngine:
    import os
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = LanguageEngine(model=os.getenv("MODEL_WILHELMINA_MAIN", model_env or "gpt-4o-mini"))
    return _engine_singleton
'@ | Set-Content -Path .\wilhelmina\services\language_engine.py -Encoding UTF8

# Oracles cog
@'
from __future__ import annotations
import random
import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
from wilhelmina.services.language_engine import get_engine

DICE_CHOICES = [4, 6, 8, 10, 12, 20]

def _haunted_embed(title: str, desc: str) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=0x6B46C1)
    e.set_footer(text="⛧ Wilhelmina // Grand Coven")
    return e

class Oracles(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.engine = get_engine()

    @app_commands.command(name="roll", description="Roll one of six witchy dice.")
    @app_commands.describe(dice="Choose a die.")
    @app_commands.choices(dice=[app_commands.Choice(name=f"d{s}", value=s) for s in DICE_CHOICES])
    async def roll(self, interaction: discord.Interaction, dice: app_commands.Choice[int]):
        sides = dice.value
        result = random.randint(1, sides)
        line = await self.engine.compose(
            place="embed",
            intent="roll-line",
            variables={"sides": sides, "result": result},
            fallback="The bones clatter; fate approves."
        )
        body = f"**You rolled:** d{sides} → **{result}**\n{line}"
        await interaction.response.send_message(embed=_haunted_embed("Dice Divination", body))

    @app_commands.command(name="8ball", description="Ask Wilhelmina the eldritch 8-ball.")
    @app_commands.describe(question="What do you seek?")
    async def eightball(self, interaction: discord.Interaction, question: str):
        r = random.random()
        verdict: Literal["Affirmative", "Vague", "Negative"]
        if r < 0.50: verdict = "Affirmative"
        elif r < 0.75: verdict = "Vague"
        else: verdict = "Negative"

        line = await self.engine.compose(
            place="embed",
            intent="8ball-line",
            variables={"verdict": verdict, "question": question},
            fallback={"Affirmative":"Yes—the current runs with you.",
                      "Vague":"Clouded—the mirror will not settle.",
                      "Negative":"No—the gate is shut."}[verdict]
        )
        body = f"**Question:** {question}\n**Answer:** {line}"
        await interaction.response.send_message(embed=_haunted_embed("Witch’s 8-Ball", body))

    @app_commands.command(name="misfortune-cookie", description="Crack a cursed cookie.")
    async def misfortune_cookie(self, interaction: discord.Interaction):
        line = await self.engine.compose(
            place="embed",
            intent="misfortune-cookie",
            variables={},
            fallback=random.choice([
                "Beware the door that opens by itself.",
                "Your shadow will learn a new name.",
                "A promise you forgot did not forget you.",
            ])
        )
        await interaction.response.send_message(embed=_haunted_embed("Misfortune Cookie", line))

async def setup(bot: commands.Bot):
    await bot.add_cog(Oracles(bot))
'@ | Set-Content -Path .\wilhelmina\cogs\oracles.py -Encoding UTF8

# Bot entrypoint
@'
import os, asyncio, discord
from discord.ext import commands

INTENTS = discord.Intents.default()
INTENTS.message_content = False
INTENTS.members = True
INTENTS.voice_states = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (latency {bot.latency*1000:.0f}ms)")
    await bot.tree.sync()

async def _load():
    await bot.load_extension("wilhelmina.cogs.oracles")

def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_BOT_TOKEN in environment.")
    asyncio.run(_load())
    bot.run(token)

if __name__ == "__main__":
    main()
'@ | Set-Content -Path .\wilhelmina\bot\main.py -Encoding UTF8

# 8-ball weight smoke test
@'
from collections import Counter
import random

def pick():
    r = random.random()
    if r < 0.50: return "A"
    elif r < 0.75: return "V"
    else: return "N"

def test_weights():
    random.seed(42)
    N = 100_000
    c = Counter(pick() for _ in range(N))
    assert 0.48 <= c["A"]/N <= 0.52
    assert 0.23 <= c["V"]/N <= 0.27
    assert 0.23 <= c["N"]/N <= 0.27
'@ | Set-Content -Path .\tests\test_8ball_weights.py -Encoding UTF8

# Create venv and install deps
Write-Host "==> Creating virtual environment (.venv) and installing dependencies ..."
$py = (Get-Command py -ErrorAction SilentlyContinue)
$pythonCmd = $null
if ($py) { $pythonCmd = "py" } else {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { $pythonCmd = "python" } else { throw "Python not found. Install Python 3.11+." }
}

& $pythonCmd -3.11 -m venv .venv
$venvPy = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "Venv python not found at $venvPy" }

& $venvPy -m pip install -U pip
& $venvPy -m pip install discord.py==2.4.0 apscheduler==3.10.4 sqlmodel==0.0.18 aiosqlite==0.19.0 `
                                pydantic-settings==2.4.0 httpx==0.27.2 openai==1.43.0 `
                                ruff==0.6.7 mypy==1.11.2 pytest==8.3.3 pre-commit==3.8.0 python-dotenv==1.0.1

# Commit changes
Write-Host "==> Committing scaffold and features ..."
Invoke-Git @("add",".")
Invoke-Git @("commit","-m","feat: language engine + oracles (/roll, /8ball 50/25/25, misfortune-cookie)") | Out-Null

Write-Host "`n==> DONE."
Write-Host "Next steps:"
Write-Host "  1) Set env vars (in this PowerShell session):"
Write-Host '     $env:DISCORD_BOT_TOKEN = "<your-bot-token>"; $env:OPENAI_API_KEY = "<your-openai-key>"; $env:MODEL_WILHELMINA_MAIN = "gpt-4o-mini"'
Write-Host "  2) (Optional) Run tests:"
Write-Host "     .\.venv\Scripts\python.exe -m pytest"
Write-Host "  3) Launch the bot:"
Write-Host "     .\.venv\Scripts\python.exe -m wilhelmina.bot.main"
Write-Host "  4) Push branch:"
Write-Host "     git push -u origin $branch"
