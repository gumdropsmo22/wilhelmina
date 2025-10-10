import discord
from discord import app_commands
from discord.ext import commands

class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Latency check.")
    async def ping(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True, thinking=False)
        except discord.InteractionResponded:
            pass
        ms = round(self.bot.latency * 1000)
        embed = discord.Embed(title="Ping", description=f"Latency: {ms} ms")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ping.error
    async def ping_error(self, interaction: discord.Interaction, error: Exception):
        msg = f"Ping failed: {type(error).__name__}"
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))
