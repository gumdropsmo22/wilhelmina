"""STUB: broadcasts cog to be implemented later."""
from discord.ext import commands

class Broadcasts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

async def setup(bot: commands.Bot):
    await bot.add_cog(Broadcasts(bot))
