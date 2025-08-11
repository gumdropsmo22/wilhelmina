"""STUB: onboarding cog to be implemented later."""
from discord.ext import commands

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
