from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.fortune import generate_fortune
from utils import embeds


class Fortune(commands.Cog):
    """Standalone fortune command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="fortune", description="Crack open a strange fortune from Wilhelmina.")
    async def fortune(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        fortune_text = await generate_fortune()
        embed = embeds.system_embed(header="▒▒ FORTUNE ▒▒", description=fortune_text)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fortune(bot))
