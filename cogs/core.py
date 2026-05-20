from __future__ import annotations

import platform
import time

import discord
from discord import app_commands
from discord.ext import commands


def _format_uptime(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


class Core(commands.Cog):
    """Core user-facing runtime commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="about", description="About Wilhelmina.")
    async def about(self, interaction: discord.Interaction) -> None:
        settings = getattr(self.bot, "settings", None)
        app_env = getattr(settings, "app_env", "unknown")
        server_mode = getattr(settings, "server_mode", "dedicated")
        sync_mode = getattr(settings, "command_sync_mode", "unknown")

        message = (
            "**Wilhelmina** runtime is online.\n"
            f"Python `{platform.python_version()}` • discord.py `{discord.__version__}`\n"
            f"Environment `{app_env}` • server mode `{server_mode}` • sync `{sync_mode}`"
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="uptime", description="Show bot uptime.")
    async def uptime(self, interaction: discord.Interaction) -> None:
        started = getattr(self.bot, "start_ts", time.time())
        seconds = int(time.time() - started)
        await interaction.response.send_message(f"Uptime: {_format_uptime(seconds)}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Core(bot))
