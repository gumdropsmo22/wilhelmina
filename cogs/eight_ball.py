from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.eight_ball import choose_intent, format_question, generate_answer
from utils import embeds


class EightBall(commands.Cog):
    """Standalone Magic 8-Ball command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Answers a question with suspicious confidence.")
    @app_commands.describe(question="Your yes/no question for Wilhelmina.")
    async def eight_ball(self, interaction: discord.Interaction, question: str) -> None:
        if question is None or question.strip() == "":
            embed = embeds.system_embed(
                header="▒▒ 8-BALL ▒▒",
                description="Ask a question first. Even mystery needs input.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        intent = choose_intent()
        answer = await generate_answer(intent)
        description = f"Q: {format_question(question)}\nA: {answer}"
        embed = embeds.system_embed(header="▒▒ 8-BALL ▒▒", description=description)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EightBall(bot))
