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
