from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services import audit_log, broadcasts, guild_config
from services.database import initialize_database, managed_connection

logger = logging.getLogger("wilhelmina.broadcasts")

SEGMENT_CHOICES = [
    app_commands.Choice(name="morning", value="morning"),
    app_commands.Choice(name="evening", value="evening"),
]
ENABLE_CHOICES = [
    app_commands.Choice(name="morning", value="morning"),
    app_commands.Choice(name="evening", value="evening"),
    app_commands.Choice(name="all", value="all"),
]
CHANNEL_TARGET_CHOICES = [
    app_commands.Choice(name="default", value="default"),
    app_commands.Choice(name="morning", value="morning"),
    app_commands.Choice(name="evening", value="evening"),
]


def _format_channel(channel_id: int | None) -> str:
    return f"<#{channel_id}>" if channel_id else "unset"


def _format_bool(value: bool) -> str:
    return "enabled" if value else "disabled"


def _format_settings(settings: broadcasts.BroadcastSettings) -> str:
    lines = [
        "**Scheduled Daily Broadcasts**",
        "```txt",
        f"timezone          = {settings.timezone}",
        f"default_channel   = {settings.default_channel_id or 'unset'}",
        f"morning_channel   = {settings.morning_channel_id or 'default'}",
        f"evening_channel   = {settings.evening_channel_id or 'default'}",
        f"morning           = {_format_bool(settings.morning_enabled)} at {settings.morning_time}",
        f"evening           = {_format_bool(settings.evening_enabled)} at {settings.evening_time}",
        f"news_provider     = {settings.news_provider}",
        f"astronomy_provider= {settings.astronomy_provider}",
        f"sky_provider      = {settings.sky_provider}",
        f"morning_categories= {settings.morning_categories}",
        f"evening_categories= {settings.evening_categories}",
        "```",
    ]
    return "\n".join(lines)


def _format_runs(runs: list[broadcasts.BroadcastRun]) -> str:
    if not runs:
        return "No broadcast runs recorded yet. Pristine. Suspicious."
    lines = ["```txt"]
    for run in runs:
        fallback = " fallback" if run.fallback_used else ""
        message = f" message={run.message_id}" if run.message_id else ""
        error = f" error={run.error_code}" if run.error_code else ""
        lines.append(
            f"#{run.id} {run.logical_date} {run.segment}/{run.run_type} "
            f"status={run.status}{fallback}{message}{error}"
        )
    lines.append("```")
    return "\n".join(lines)


@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
class BroadcastAdmin(commands.GroupCog, group_name="broadcast-admin"):
    """Admin controls for scheduled morning and evening broadcasts."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.broadcast_scheduler.start()

    def cog_unload(self) -> None:
        self.broadcast_scheduler.cancel()

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

        if home_guild_id is None:
            await interaction.response.send_message(
                "Cannot resolve a guild. Set `HOME_GUILD_ID` before using broadcast commands.",
                ephemeral=True,
            )
            return None
        if interaction_guild_id is None or int(interaction_guild_id) != int(home_guild_id):
            await interaction.response.send_message(
                "Run this command inside Wilhelmina's configured home guild.",
                ephemeral=True,
            )
            return None
        return int(home_guild_id)

    async def _guard_admin_home_guild(self, interaction: discord.Interaction) -> int | None:
        if await self._reject_non_admin(interaction):
            return None
        return await self._resolve_guild_id(interaction)

    def _ensure_settings(self, guild_id: int) -> broadcasts.BroadcastSettings:
        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            return broadcasts.ensure_broadcast_settings(connection, guild_id)

    def _record_settings_audit(
        self,
        *,
        guild_id: int,
        actor_user_id: int,
        action: str,
        before: broadcasts.BroadcastSettings | None,
        after: broadcasts.BroadcastSettings | None,
    ) -> None:
        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            audit_log.record_audit_event(
                connection,
                guild_id=guild_id,
                actor_user_id=actor_user_id,
                action=action,
                target="broadcast_settings",
                before=broadcasts.settings_to_audit_dict(before),
                after=broadcasts.settings_to_audit_dict(after),
            )

    def _configured_channel_id(
        self,
        guild_id: int,
        settings: broadcasts.BroadcastSettings,
        segment: str,
    ) -> int | None:
        configured = settings.channel_id_for(segment)
        if configured is not None:
            return configured
        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            config = guild_config.get_guild_config(connection, guild_id)
        return config.broadcast_channel_id if config else None

    def _resolve_text_channel(
        self,
        guild_id: int,
        settings: broadcasts.BroadcastSettings,
        segment: str,
        override: discord.TextChannel | None = None,
    ) -> discord.TextChannel | None:
        if override is not None:
            return override
        channel_id = self._configured_channel_id(guild_id, settings, segment)
        if channel_id is None:
            return None
        guild = self.bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id) if guild else self.bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def _build_draft(
        self,
        guild_id: int,
        settings: broadcasts.BroadcastSettings,
        segment: str,
    ) -> broadcasts.BroadcastDraft:
        database_path = self._database_path()
        evidence = broadcasts.build_empty_evidence(settings, segment)
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            recent_hashes = broadcasts.list_recent_text_hashes(connection, guild_id, segment)
        return await broadcasts.generate_broadcast_draft(
            settings=settings,
            evidence=evidence,
            recent_hashes=recent_hashes,
        )

    @tasks.loop(minutes=1)
    async def broadcast_scheduler(self) -> None:
        settings = getattr(self.bot, "settings", None)
        guild_id = getattr(settings, "home_guild_id", None)
        if guild_id is None:
            return
        await self._tick_guild(int(guild_id))

    @broadcast_scheduler.before_loop
    async def before_broadcast_scheduler(self) -> None:
        await self.bot.wait_until_ready()

    async def _tick_guild(self, guild_id: int) -> None:
        try:
            settings = self._ensure_settings(guild_id)
        except Exception:
            logger.exception("broadcast_settings_load_failed guild_id=%s", guild_id)
            return

        now = datetime.now(ZoneInfo(settings.timezone))
        for segment in broadcasts.VALID_SEGMENTS:
            if not settings.is_enabled(segment):
                continue
            if now.strftime("%H:%M") != settings.time_for(segment):
                continue
            await self._run_scheduled(guild_id, settings, segment, now=now)

    async def _run_scheduled(
        self,
        guild_id: int,
        settings: broadcasts.BroadcastSettings,
        segment: str,
        *,
        now: datetime,
    ) -> None:
        scheduled_for = broadcasts.local_broadcast_datetime(settings, segment, now.date()).isoformat(
            timespec="seconds"
        )
        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            run = broadcasts.claim_scheduled_run(
                connection,
                guild_id=guild_id,
                segment=segment,
                logical_date=now.date().isoformat(),
                scheduled_for=scheduled_for,
            )
        if run is None:
            return

        evidence = broadcasts.build_empty_evidence(settings, segment, now=now)
        if not broadcasts.has_publishable_evidence(evidence):
            with managed_connection(database_path) as connection:
                broadcasts.record_broadcast_run_result(
                    connection,
                    run.id,
                    status="skipped",
                    error_code="no_verified_sources",
                )
            return

        channel = self._resolve_text_channel(guild_id, settings, segment)
        if channel is None:
            with managed_connection(database_path) as connection:
                broadcasts.record_broadcast_run_result(
                    connection,
                    run.id,
                    status="failed",
                    error_code="missing_channel",
                )
            return

        draft = await self._build_draft(guild_id, settings, segment)
        try:
            message = await channel.send(draft.content)
        except discord.DiscordException:
            logger.exception("broadcast_send_failed guild_id=%s segment=%s", guild_id, segment)
            with managed_connection(database_path) as connection:
                broadcasts.record_broadcast_run_result(
                    connection,
                    run.id,
                    status="failed",
                    fallback_used=draft.fallback_used,
                    error_code="discord_send_failed",
                )
            return

        with managed_connection(database_path) as connection:
            broadcasts.record_broadcast_run_result(
                connection,
                run.id,
                status="posted",
                message_id=message.id,
                fallback_used=draft.fallback_used,
            )
            broadcasts.record_text_history(
                connection,
                guild_id=guild_id,
                segment=segment,
                logical_date=evidence.logical_date,
                content=draft.content,
            )

    @app_commands.command(name="status", description="Show scheduled broadcast settings and recent runs.")
    async def status(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard_admin_home_guild(interaction)
        if guild_id is None:
            return
        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            settings = broadcasts.ensure_broadcast_settings(connection, guild_id)
            runs = broadcasts.list_recent_runs(connection, guild_id, limit=5)
        await interaction.response.send_message(
            f"{_format_settings(settings)}\n{_format_runs(runs)}",
            ephemeral=True,
        )

    @app_commands.command(name="preview", description="Preview a generated broadcast without posting it.")
    @app_commands.choices(segment=SEGMENT_CHOICES)
    async def preview(
        self,
        interaction: discord.Interaction,
        segment: app_commands.Choice[str],
    ) -> None:
        guild_id = await self._guard_admin_home_guild(interaction)
        if guild_id is None:
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        settings = self._ensure_settings(guild_id)
        draft = await self._build_draft(guild_id, settings, segment.value)
        diagnostics = "fallback=yes" if draft.fallback_used else "fallback=no"
        if draft.validation_errors:
            diagnostics += f" validation={','.join(draft.validation_errors)}"
        await interaction.edit_original_response(content=f"**Preview only** `{diagnostics}`\n\n{draft.content}")

    @app_commands.command(name="send-test", description="Post a test broadcast now.")
    @app_commands.choices(segment=SEGMENT_CHOICES)
    async def send_test(
        self,
        interaction: discord.Interaction,
        segment: app_commands.Choice[str],
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild_id = await self._guard_admin_home_guild(interaction)
        if guild_id is None:
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        settings = self._ensure_settings(guild_id)
        target = self._resolve_text_channel(guild_id, settings, segment.value, override=channel)
        if target is None:
            await interaction.edit_original_response(
                content="No broadcast channel is configured. Set one with `/broadcast-admin set-channel` first."
            )
            return

        draft = await self._build_draft(guild_id, settings, segment.value)
        try:
            message = await target.send(f"**TEST BROADCAST**\n{draft.content}")
        except discord.DiscordException as exc:
            await interaction.edit_original_response(content=f"Discord send failed: {exc}")
            return

        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            broadcasts.record_test_run(
                connection,
                guild_id=guild_id,
                segment=segment.value,
                logical_date=broadcasts.current_local_date(settings),
                message_id=message.id,
                fallback_used=draft.fallback_used,
            )
            broadcasts.record_text_history(
                connection,
                guild_id=guild_id,
                segment=segment.value,
                logical_date=broadcasts.current_local_date(settings),
                content=draft.content,
            )
        await interaction.edit_original_response(
            content=f"Test {segment.value} broadcast posted to {_format_channel(target.id)}."
        )

    @app_commands.command(name="enable", description="Enable scheduled broadcast posting.")
    @app_commands.choices(segment=ENABLE_CHOICES)
    async def enable(
        self,
        interaction: discord.Interaction,
        segment: app_commands.Choice[str],
    ) -> None:
        await self._set_enabled(interaction, segment.value, enabled=True)

    @app_commands.command(name="disable", description="Disable scheduled broadcast posting.")
    @app_commands.choices(segment=ENABLE_CHOICES)
    async def disable(
        self,
        interaction: discord.Interaction,
        segment: app_commands.Choice[str],
    ) -> None:
        await self._set_enabled(interaction, segment.value, enabled=False)

    async def _set_enabled(
        self,
        interaction: discord.Interaction,
        segment: str,
        *,
        enabled: bool,
    ) -> None:
        guild_id = await self._guard_admin_home_guild(interaction)
        if guild_id is None:
            return
        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            if segment == "all":
                before, after = broadcasts.update_broadcast_settings(
                    connection,
                    guild_id,
                    {"morning_enabled": enabled, "evening_enabled": enabled},
                )
            else:
                before, after = broadcasts.set_segment_enabled(connection, guild_id, segment, enabled)
        self._record_settings_audit(
            guild_id=guild_id,
            actor_user_id=interaction.user.id,
            action="broadcast_enable" if enabled else "broadcast_disable",
            before=before,
            after=after,
        )
        await interaction.response.send_message(_format_settings(after), ephemeral=True)

    @app_commands.command(name="set-channel", description="Set the default, morning, or evening channel.")
    @app_commands.choices(target=CHANNEL_TARGET_CHOICES)
    async def set_channel(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        channel: discord.TextChannel,
    ) -> None:
        guild_id = await self._guard_admin_home_guild(interaction)
        if guild_id is None:
            return
        database_path = self._database_path()
        initialize_database(database_path)
        with managed_connection(database_path) as connection:
            before, after = broadcasts.set_broadcast_channel(
                connection,
                guild_id,
                target.value,
                channel.id,
            )
        self._record_settings_audit(
            guild_id=guild_id,
            actor_user_id=interaction.user.id,
            action="broadcast_set_channel",
            before=before,
            after=after,
        )
        await interaction.response.send_message(
            f"Broadcast {target.value} channel set to {_format_channel(channel.id)}.",
            ephemeral=True,
        )

    @app_commands.command(name="set-time", description="Set a segment time in 24-hour HH:MM format.")
    @app_commands.choices(segment=SEGMENT_CHOICES)
    async def set_time(
        self,
        interaction: discord.Interaction,
        segment: app_commands.Choice[str],
        time: str,
    ) -> None:
        guild_id = await self._guard_admin_home_guild(interaction)
        if guild_id is None:
            return
        database_path = self._database_path()
        initialize_database(database_path)
        try:
            with managed_connection(database_path) as connection:
                before, after = broadcasts.set_segment_time(connection, guild_id, segment.value, time)
        except broadcasts.BroadcastError as exc:
            await interaction.response.send_message(f"Broadcast config error: {exc}", ephemeral=True)
            return
        self._record_settings_audit(
            guild_id=guild_id,
            actor_user_id=interaction.user.id,
            action="broadcast_set_time",
            before=before,
            after=after,
        )
        await interaction.response.send_message(_format_settings(after), ephemeral=True)

    @app_commands.command(name="set-timezone", description="Set the broadcast timezone.")
    async def set_timezone(self, interaction: discord.Interaction, timezone: str) -> None:
        guild_id = await self._guard_admin_home_guild(interaction)
        if guild_id is None:
            return
        database_path = self._database_path()
        initialize_database(database_path)
        try:
            with managed_connection(database_path) as connection:
                before, after = broadcasts.set_broadcast_timezone(connection, guild_id, timezone)
        except broadcasts.BroadcastError as exc:
            await interaction.response.send_message(f"Broadcast config error: {exc}", ephemeral=True)
            return
        self._record_settings_audit(
            guild_id=guild_id,
            actor_user_id=interaction.user.id,
            action="broadcast_set_timezone",
            before=before,
            after=after,
        )
        await interaction.response.send_message(_format_settings(after), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BroadcastAdmin(bot))
