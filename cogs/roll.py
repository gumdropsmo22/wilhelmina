from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.rolls import number_lore, roll_die
from utils import embeds


class Roll(commands.Cog):
    """Standalone dice rolling command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll a die and receive Wilhelmina's reading.")
    @app_commands.describe(sides="Number of sides on the die (2-1000).")
    async def roll(
        self,
        interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 1000],
    ) -> None:
        result = roll_die(sides)
        description = f"You rolled **d{sides} → {result}**\n{result}. {number_lore(result)}"
        embed = embeds.system_embed(
            header="▒▒ ROLL ▒▒",
            description=description,
            include_trace=True,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roll(bot))
