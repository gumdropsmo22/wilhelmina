from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands


def _format_uptime(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def _format_sequence(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


class Admin(commands.GroupCog, group_name="admin"):
    """Admin-only diagnostics and runtime controls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _reject_non_admin(self, interaction: discord.Interaction) -> bool:
        permissions = getattr(interaction.user, "guild_permissions", None)
        if not permissions or not permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return True
        return False

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="diagnostics", description="Show Wilhelmina runtime diagnostics.")
    async def diagnostics(self, interaction: discord.Interaction) -> None:
        if await self._reject_non_admin(interaction):
            return

        settings = self.bot.settings
        report = getattr(
            self.bot,
            "cog_load_report",
            {"loaded": [], "skipped": [], "failed": []},
        )
        uptime_seconds = int(time.time() - getattr(self.bot, "start_ts", time.time()))

        message = (
            "**Wilhelmina diagnostics**\n"
            "```txt\n"
            f"app_env        = {settings.app_env}\n"
            f"server_mode    = {settings.server_mode}\n"
            f"sync_mode      = {settings.command_sync_mode}\n"
            f"home_guild_id  = {settings.home_guild_id or 'unset'}\n"
            f"uptime         = {_format_uptime(uptime_seconds)}\n"
            f"loaded_cogs    = {_format_sequence(report.get('loaded', []))}\n"
            f"skipped_cogs   = {_format_sequence(report.get('skipped', []))}\n"
            f"failed_cogs    = {_format_sequence(report.get('failed', []))}\n"
            "```"
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="features", description="Show enabled and disabled Wilhelmina features.")
    async def features(self, interaction: discord.Interaction) -> None:
        if await self._reject_non_admin(interaction):
            return

        settings = self.bot.settings
        lines = ["**Wilhelmina features**", "```txt"]
        for flag in settings.cog_flags:
            status = "enabled" if settings.is_cog_enabled(flag.extension) else "disabled"
            required = "required" if flag.required else "optional"
            lines.append(f"{flag.env_var:<20} {status:<8} {required:<8} {flag.extension}")
        lines.append("```")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="sync", description="Resync Wilhelmina slash commands.")
    async def sync(self, interaction: discord.Interaction) -> None:
        if await self._reject_non_admin(interaction):
            return

        settings = self.bot.settings
        mode = settings.command_sync_mode

        if mode == "off":
            await interaction.response.send_message(
                "Command sync is disabled by `COMMAND_SYNC_MODE=off`.",
                ephemeral=True,
            )
            return

        if mode == "auto":
            mode = "guild" if settings.home_guild_id else "global"

        if mode == "guild":
            if settings.home_guild_id is None:
                await interaction.response.send_message(
                    "Cannot sync: `HOME_GUILD_ID` is not set.",
                    ephemeral=True,
                )
                return

            guild = discord.Object(id=settings.home_guild_id)
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            await interaction.response.send_message(
                f"Synced {len(synced)} command(s) to home guild `{settings.home_guild_id}`.",
                ephemeral=True,
            )
            return

        synced = await self.bot.tree.sync()
        await interaction.response.send_message(
            f"Synced {len(synced)} command(s) globally. Global sync can take time to propagate.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
