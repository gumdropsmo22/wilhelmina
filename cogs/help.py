from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds

log = logging.getLogger(__name__)


class Help(commands.Cog):
    """Provides the dynamic /help command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="List available bot commands.")
    async def help(self, interaction: discord.Interaction):
        """Respond with a list of available slash commands."""
        log.info("/help invoked by %s", interaction.user)

        cmds = interaction.client.tree.get_commands()
        visible: list[app_commands.Command] = []
        for cmd in cmds:
            if not isinstance(cmd, app_commands.Command):
                continue
            if cmd.extras.get("hidden"):
                continue
            perms = getattr(cmd, "default_permissions", None)
            if perms and perms.administrator:
                continue
            visible.append(cmd)

        visible.sort(key=lambda c: c.name.lower())
        lines = [f"/{c.name} — {c.description}" for c in visible]
        description = "\n".join(lines) if lines else "No commands available."

        embed = embeds.system_embed(header="▒▒ COMMANDS ▒▒", description=description)
        footer_base = embed.footer.text or ""
        footer_text = (
            f"{footer_base} • This list is visible only to you"
            if footer_base
            else "This list is visible only to you"
        )
        embed.set_footer(text=footer_text, icon_url=embed.footer.icon_url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
