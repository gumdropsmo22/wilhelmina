"""STUB: mood cog to be implemented later."""
from discord.ext import commands

class Mood(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

async def setup(bot: commands.Bot):
    await bot.add_cog(Mood(bot))
