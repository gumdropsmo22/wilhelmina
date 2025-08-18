from __future__ import annotations
import logging, discord
from discord import app_commands
from discord.ext import commands
from utils import embeds
from utils.respond import reply

log = logging.getLogger(__name__)

class Errors(commands.Cog):
    """Centralized app command error handler."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_app_command_error")
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "You lack the required permissions."
        elif isinstance(error, app_commands.CheckFailure):
            msg = "This command cannot be used here."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"On cooldown. Try again in {error.retry_after:.1f}s."
        else:
            msg = "Something went wrong. The coven is investigating."
            log.exception("Command error: %s", error)
        e = embeds.system_embed(header="Help", description=msg)
        await reply(interaction, embed=e, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Errors(bot))
