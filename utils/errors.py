import logging
import discord
from discord import app_commands
from discord.ext import commands
from .embeds import system_embed

log = logging.getLogger(__name__)


def register_error_handler(bot: commands.Bot) -> None:
    """Register a global application command error handler on the bot."""

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Global handler for unhandled application command errors."""
        # Log the full exception with traceback
        log.error("Unhandled application command error", exc_info=error)

        description = (
            "Wilhelmina encountered a disturbance in the æther.\n"
            f"`{error.__class__.__name__}`"
        )
        embed = system_embed(header="▒▒ ERROR ▒▒", description=description)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            # If we can't send the error message, silently ignore
            pass
