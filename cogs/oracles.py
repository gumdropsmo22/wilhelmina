import json
import random
import pathlib
import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds, persona
from config import settings


DATA = pathlib.Path("data")


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True


def _lore_for_number(n: int) -> str:
    try:
        lore_map = json.loads((DATA / "roll_lore.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        lore_map = {}
    if str(n) in lore_map:
        return lore_map[str(n)]
    if _is_prime(n):
        return "Prime and indivisible—alone in the void."
    if n % 2 == 0:
        return "Even and dull—symmetry bores me."
    return "Odd and unruly—just my style."


class Oracles(commands.Cog):
    """Cog registering oracle slash commands: /roll, /8ball, and /fortune."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # /roll command: roll a die and give an ominous interpretation
    @app_commands.command(name="roll", description="Roll a divination die and receive Wilhelmina's reading.")
    @app_commands.describe(sides="Number of sides on the die (2-1000).")
    async def roll(self, interaction: discord.Interaction, sides: app_commands.Range[int, 2, 1000]):
        # Perform the random roll
        result = random.randint(1, sides)
        # Construct the embed content
        header = "▒▒ DIVINATION: ROLL ▒▒"
        dice_info = f"You rolled **d{sides} → {result}**"
        lore_line = persona.number_lore(result)
        description = f"{dice_info}\n{result}. {lore_line}"
        # Build the embed with a trace field for extra glitchy detail
        embed = embeds.system_embed(header=header, description=description, include_trace=True)
        await interaction.response.send_message(embed=embed)

    # /8ball command: answer a yes/no question with Wilhelmina's oracle
    @app_commands.command(name="8ball", description="Ask the Oracle a question and receive Wilhelmina's answer.")
    @app_commands.describe(question="Your yes/no question for Wilhelmina's oracle.")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        # Handle missing question (shouldn't happen with required param, but just in case)
        if question is None or question.strip() == "":
            scold = "You dare seek wisdom without a question? Pathetic."
            embed = embeds.system_embed(header="▒▒ ORACLE: 8-BALL ▒▒", description=f"A: {scold}")
            await interaction.response.send_message(embed=embed)
            return
        # Determine intent with weighted probabilities: 10 yes, 10 no, 5 maybe, 5 ask-again
        categories = (["yes"] * 10) + (["no"] * 10) + (["maybe"] * 5) + (["ask-again"] * 5)
        intent = random.choice(categories)
        answer = persona.generate_eight_ball(intent)
        # Format the question and answer in the embed description
        q_text = question.strip()
        # Wrap question in quotes (choose quote style that avoids duplication of any internal quotes)
        if '"' in q_text and "'" not in q_text:
            q_display = f"'{q_text}'"
        else:
            q_display = f'"{q_text}"'
        description = f"Q: {q_display}\nA: {answer}"
        embed = embeds.system_embed(header="▒▒ ORACLE: 8-BALL ▒▒", description=description)
        await interaction.response.send_message(embed=embed)

    # /fortune command: deliver a cursed fortune cookie line
    @app_commands.command(name="fortune", description="Crack open a cursed fortune cookie from Wilhelmina.")
    async def fortune(self, interaction: discord.Interaction):
        fortune_text = persona.generate_fortune()
        embed = embeds.system_embed(header="▒▒ FORTUNE ▒▒", description=fortune_text)
        await interaction.response.send_message(embed=embed)


# Cog setup function (registers the cog if embeds-only mode is active)
async def setup(bot: commands.Bot):
    if getattr(settings, "EMBEDS_ONLY", True):
        await bot.add_cog(Oracles(bot))
