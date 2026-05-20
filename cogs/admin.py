from __future__ import annotations

import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from services import audit_log, guild_config
from services.database import initialize_database, managed_connection

ROLE_FIELD_CHOICES = [
    app_commands.Choice(name="admin_role_id", value="admin_role_id"),
    app_commands.Choice(name="member_role_id", value="member_role_id"),
    app_commands.Choice(name="pending_role_id", value="pending_role_id"),
]
CHANNEL_FIELD_CHOICES = [
    app_commands.Choice(name="welcome_channel_id", value="welcome_channel_id"),
    app_commands.Choice(name="onboarding_channel_id", value="onboarding_channel_id"),
    app_commands.Choice(name="broadcast_channel_id", value="broadcast_channel_id"),
    app_commands.Choice(name="admin_log_channel_id", value="admin_log_channel_id"),
]
CLEAR_FIELD_CHOICES = ROLE_FIELD_CHOICES + CHANNEL_FIELD_CHOICES + [
    app_commands.Choice(name="timezone", value="timezone"),
]

ROLE_FIELD_ORDER = ("admin_role_id", "member_role_id", "pending_role_id")
CHANNEL_FIELD_ORDER = (
    "welcome_channel_id",
    "onboarding_channel_id",
    "broadcast_channel_id",
    "admin_log_channel_id",
)


def _format_uptime(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def _format_sequence(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _format_config_value(value: int | str | None) -> str:
    return str(value) if value is not None else "unset"


def _format_config(config: guild_config.GuildConfig | None) -> str:
    if config is None:
        return "No guild configuration has been stored yet."

    lines = [
        "```txt",
        f"guild_id              = {config.guild_id}",
        f"admin_role_id         = {_format_config_value(config.admin_role_id)}",
        f"member_role_id        = {_format_config_value(config.member_role_id)}",
        f"pending_role_id       = {_format_config_value(config.pending_role_id)}",
        f"welcome_channel_id    = {_format_config_value(config.welcome_channel_id)}",
        f"onboarding_channel_id = {_format_config_value(config.onboarding_channel_id)}",
        f"broadcast_channel_id  = {_format_config_value(config.broadcast_channel_id)}",
        f"admin_log_channel_id  = {_format_config_value(config.admin_log_channel_id)}",
        f"timezone              = {config.timezone}",
        f"created_at            = {config.created_at}",
        f"updated_at            = {config.updated_at}",
        "```",
    ]
    return "\n".join(lines)


class Admin(commands.GroupCog, group_name="admin"):
    """Admin-only diagnostics, runtime controls, and guild configuration."""

    config = app_commands.Group(
        name="config",
        description="Manage Wilhelmina's stored guild configuration.",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _database_path(self) -> Path:
        return Path(self.bot.settings.database_path)

    async def _reject_non_admin(self, interaction: discord.Interaction) -> bool:
        permissions = getattr(interaction.user, "guild_permissions", None)
        if not permissions or not permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return True
        return False

    async def _resolve_guild_id(self, interaction: discord.Interaction) -> int | None:
        settings = self.bot.settings
        home_guild_id = getattr(settings, "home_guild_id", None)
        interaction_guild_id = interaction.guild_id

        if home_guild_id is not None and interaction_guild_id is not None:
            if int(interaction_guild_id) != int(home_guild_id):
                await interaction.response.send_message(
                    "This command only runs in Wilhelmina's configured home guild.",
                    ephemeral=True,
                )
                return None

        guild_id = interaction_guild_id or home_guild_id
        if guild_id is None:
            await interaction.response.send_message(
                "Cannot resolve a guild. Set `HOME_GUILD_ID` and run this inside the server.",
                ephemeral=True,
            )
            return None

        return int(guild_id)

    async def _send_config_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        await interaction.response.send_message(f"Config error: {error}", ephemeral=True)

    def _record_config_audit(
        self,
        connection,
        *,
        guild_id: int,
        actor_user_id: int,
        action: str,
        target: str,
        before: guild_config.GuildConfig | None,
        after: guild_config.GuildConfig | None,
    ) -> None:
        audit_log.record_audit_event(
            connection,
            guild_id=guild_id,
            actor_user_id=actor_user_id,
            action=action,
            target=target,
            before=guild_config.config_to_audit_dict(before),
            after=guild_config.config_to_audit_dict(after),
        )

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
            f"database_path  = {settings.database_path}\n"
            f"uptime         = {_format_uptime(uptime_seconds)}\n"
            f"loaded_cogs    = {_format_sequence(report.get('loaded', []))}\n"
            f"skipped_cogs   = {_format_sequence(report.get('skipped', []))}\n"
            f"failed_cogs    = {_format_sequence(report.get('failed', []))}\n"
            "```"
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(
        name="features",
        description="Show enabled and disabled Wilhelmina features.",
    )
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

    @config.command(name="view", description="View Wilhelmina's stored guild configuration.")
    @app_commands.default_permissions(administrator=True)
    async def config_view(self, interaction: discord.Interaction) -> None:
        if await self._reject_non_admin(interaction):
            return

        guild_id = await self._resolve_guild_id(interaction)
        if guild_id is None:
            return

        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            config = guild_config.get_guild_config(connection, guild_id)

        await interaction.response.send_message(
            f"**Wilhelmina guild config**\n{_format_config(config)}",
            ephemeral=True,
        )

    @config.command(name="set-role", description="Store one configured guild role.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        field="Role config field to update.",
        role="Existing Discord role to store.",
    )
    @app_commands.choices(field=ROLE_FIELD_CHOICES)
    async def config_set_role(
        self,
        interaction: discord.Interaction,
        field: str,
        role: discord.Role,
    ) -> None:
        if await self._reject_non_admin(interaction):
            return

        guild_id = await self._resolve_guild_id(interaction)
        if guild_id is None:
            return

        database_path = self._database_path()
        initialize_database(database_path)
        try:
            with managed_connection(database_path) as connection:
                before, after = guild_config.set_role(connection, guild_id, field, role.id)
                self._record_config_audit(
                    connection,
                    guild_id=guild_id,
                    actor_user_id=interaction.user.id,
                    action="guild_config.set_role",
                    target=field,
                    before=before,
                    after=after,
                )
        except guild_config.GuildConfigError as exc:
            await self._send_config_error(interaction, exc)
            return

        await interaction.response.send_message(
            f"Stored `{field}` as role `{role.name}` (`{role.id}`).",
            ephemeral=True,
        )

    @config.command(name="set-channel", description="Store one configured guild text channel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        field="Channel config field to update.",
        channel="Existing Discord text channel to store.",
    )
    @app_commands.choices(field=CHANNEL_FIELD_CHOICES)
    async def config_set_channel(
        self,
        interaction: discord.Interaction,
        field: str,
        channel: discord.TextChannel,
    ) -> None:
        if await self._reject_non_admin(interaction):
            return

        guild_id = await self._resolve_guild_id(interaction)
        if guild_id is None:
            return

        database_path = self._database_path()
        initialize_database(database_path)
        try:
            with managed_connection(database_path) as connection:
                before, after = guild_config.set_channel(connection, guild_id, field, channel.id)
                self._record_config_audit(
                    connection,
                    guild_id=guild_id,
                    actor_user_id=interaction.user.id,
                    action="guild_config.set_channel",
                    target=field,
                    before=before,
                    after=after,
                )
        except guild_config.GuildConfigError as exc:
            await self._send_config_error(interaction, exc)
            return

        await interaction.response.send_message(
            f"Stored `{field}` as channel `{channel.name}` (`{channel.id}`).",
            ephemeral=True,
        )

    @config.command(name="set-timezone", description="Store the guild IANA timezone.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(timezone="IANA timezone name, such as UTC or Asia/Riyadh.")
    async def config_set_timezone(
        self,
        interaction: discord.Interaction,
        timezone: str,
    ) -> None:
        if await self._reject_non_admin(interaction):
            return

        guild_id = await self._resolve_guild_id(interaction)
        if guild_id is None:
            return

        database_path = self._database_path()
        initialize_database(database_path)
        try:
            with managed_connection(database_path) as connection:
                before, after = guild_config.set_timezone(connection, guild_id, timezone)
                self._record_config_audit(
                    connection,
                    guild_id=guild_id,
                    actor_user_id=interaction.user.id,
                    action="guild_config.set_timezone",
                    target="timezone",
                    before=before,
                    after=after,
                )
        except guild_config.GuildConfigError as exc:
            await self._send_config_error(interaction, exc)
            return

        await interaction.response.send_message(
            f"Stored guild timezone as `{after.timezone}`.",
            ephemeral=True,
        )

    @config.command(name="validate", description="Validate stored guild roles and channels.")
    @app_commands.default_permissions(administrator=True)
    async def config_validate(self, interaction: discord.Interaction) -> None:
        if await self._reject_non_admin(interaction):
            return

        guild_id = await self._resolve_guild_id(interaction)
        if guild_id is None:
            return

        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            config = guild_config.get_guild_config(connection, guild_id)

        if config is None:
            await interaction.response.send_message(
                "No guild configuration has been stored yet.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        issues = guild_config.validate_guild_config(
            config,
            role_exists=(lambda role_id: guild.get_role(role_id) is not None) if guild else None,
            channel_exists=(lambda channel_id: guild.get_channel(channel_id) is not None)
            if guild
            else None,
        )

        lines = ["**Wilhelmina guild config validation**", "```txt"]
        for issue in issues:
            marker = "OK" if issue.ok else "!!"
            lines.append(
                f"{marker} {issue.field:<24} "
                f"{_format_config_value(issue.value):<24} {issue.message}"
            )
        lines.append("```")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @config.command(name="clear", description="Clear stored guild config or one selected field.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        field="Optional field to clear. Leave empty to delete the full config row.",
    )
    @app_commands.choices(field=CLEAR_FIELD_CHOICES)
    async def config_clear(
        self,
        interaction: discord.Interaction,
        field: str | None = None,
    ) -> None:
        if await self._reject_non_admin(interaction):
            return

        guild_id = await self._resolve_guild_id(interaction)
        if guild_id is None:
            return

        database_path = self._database_path()
        initialize_database(database_path)
        try:
            with managed_connection(database_path) as connection:
                fields = None if field is None else [field]
                before, after = guild_config.clear_guild_config(connection, guild_id, fields)
                if before is not None:
                    self._record_config_audit(
                        connection,
                        guild_id=guild_id,
                        actor_user_id=interaction.user.id,
                        action="guild_config.clear",
                        target=field or "all",
                        before=before,
                        after=after,
                    )
        except guild_config.GuildConfigError as exc:
            await self._send_config_error(interaction, exc)
            return

        if before is None:
            await interaction.response.send_message(
                "No guild configuration existed to clear.",
                ephemeral=True,
            )
            return

        if field is None:
            message = "Deleted the stored guild configuration row."
        else:
            message = f"Cleared `{field}` from the stored guild configuration."

        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
