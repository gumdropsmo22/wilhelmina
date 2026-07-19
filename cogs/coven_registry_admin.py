from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from services import coven_registry as registry
from services import coven_registry_views as views
from services.database import initialize_database, managed_connection

CLASSIFICATION_CHOICES = [app_commands.Choice(name=value, value=value) for value in registry.VALID_CLASSIFICATIONS]
STATUS_CHOICES = [app_commands.Choice(name=value, value=value) for value in registry.VALID_STATUSES]


def _path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def _iso(value: object | None) -> str | None:
    method = getattr(value, "isoformat", None)
    return str(method()) if callable(method) else (str(value) if value is not None else None)


@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
class CovenRegistryAdmin(commands.GroupCog, group_name="registry-admin"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _guard(self, interaction: discord.Interaction) -> int | None:
        permissions = getattr(interaction.user, "guild_permissions", None)
        expected = getattr(self.bot.settings, "home_guild_id", None)
        if not permissions or not permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return None
        if expected is None or interaction.guild_id != int(expected):
            await interaction.response.send_message("Run this inside Wilhelmina's configured home guild.", ephemeral=True)
            return None
        return int(expected)

    @app_commands.command(name="bootstrap", description="Create Wilhelmina and founder Registry entries.")
    async def bootstrap(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        bot_user = self.bot.user
        if bot_user is None:
            await interaction.response.send_message("Wilhelmina is not fully online yet.", ephemeral=True)
            return
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                result = registry.bootstrap_registry(
                    connection,
                    guild_id=guild_id,
                    wilhelmina_user_id=bot_user.id,
                    founder_user_id=interaction.user.id,
                    wilhelmina_name=getattr(bot_user, "display_name", bot_user.name),
                    founder_name=getattr(interaction.user, "display_name", interaction.user.name),
                    founder_joined_at=_iso(getattr(interaction.user, "joined_at", None)),
                    actor_user_id=interaction.user.id,
                )
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        verb = "already existed" if result.already_bootstrapped else "was created"
        await interaction.response.send_message(
            f"The Coven Registry {verb}.\n"
            f"Wilhelmina: `{result.wilhelmina.display_mark}`\n"
            f"Founder: `{result.founder.display_mark}`\n"
            f"Next mark: `{registry.display_mark(result.settings.next_number)}`",
            ephemeral=True,
        )

    @app_commands.command(name="status", description="Show Registry totals and configuration.")
    async def status(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_path(self.bot))
        with managed_connection(_path(self.bot)) as connection:
            summary = registry.summarize_registry(connection, guild_id=guild_id)
        await interaction.response.send_message(
            "**Coven Registry status**\n```txt\n"
            f"total             = {summary.total}\n"
            f"active            = {summary.active}\n"
            f"pending           = {summary.pending}\n"
            f"inducted          = {summary.initiated}\n"
            f"archived          = {summary.archived}\n"
            f"banished          = {summary.banished}\n"
            f"next_number       = {summary.next_number or 'unbootstrapped'}\n"
            f"public_channel_id = {summary.public_channel_id or 'unset'}\n```",
            ephemeral=True,
        )

    @app_commands.command(name="register", description="Manually register a member as Pending.")
    async def register(self, interaction: discord.Interaction, user: discord.Member) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        if user.bot:
            await interaction.response.send_message("Bot accounts are not inducted as members.", ephemeral=True)
            return
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                result = registry.register_pending_member(
                    connection,
                    guild_id=guild_id,
                    user_id=user.id,
                    display_name=user.display_name,
                    joined_at=_iso(user.joined_at),
                    actor_user_id=interaction.user.id,
                )
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        action = "created" if result.created else "updated"
        await interaction.response.send_message(
            f"Registry entry {action}: `{result.entry.display_mark}` for {user.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="lookup", description="Open a member's full private Registry file.")
    async def lookup(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        mark: str | None = None,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        if user is None and not mark:
            await interaction.response.send_message("Provide a member or Coven Mark.", ephemeral=True)
            return
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                entry = (
                    registry.get_entry(connection, guild_id=guild_id, user_id=user.id)
                    if user is not None
                    else registry.get_entry_by_mark(connection, guild_id=guild_id, mark=mark or "")
                )
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        assert entry is not None
        await interaction.response.send_message(embed=views.admin_profile(entry), ephemeral=True)

    @app_commands.command(name="backfill", description="Register existing human members deterministically.")
    async def backfill(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None or interaction.guild is None:
            return
        members = [
            (member.id, member.display_name, _iso(member.joined_at))
            for member in interaction.guild.members
            if not member.bot and member.id != interaction.user.id
        ]
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                results = registry.backfill_members(
                    connection,
                    guild_id=guild_id,
                    members=members,
                    actor_user_id=interaction.user.id,
                )
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        created = sum(1 for result in results if result.created)
        await interaction.response.send_message(
            f"Backfill complete: {created} created, {len(results) - created} already recorded.",
            ephemeral=True,
        )

    @app_commands.command(name="set-classification", description="Change a Registry classification.")
    @app_commands.choices(classification=CLASSIFICATION_CHOICES)
    async def set_classification(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        classification: app_commands.Choice[str],
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                entry = registry.set_classification(
                    connection,
                    guild_id=guild_id,
                    user_id=user.id,
                    classification=classification.value,
                    actor_user_id=interaction.user.id,
                )
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"`{entry.display_mark}` is now classified as **{entry.classification}**.",
            ephemeral=True,
        )

    @app_commands.command(name="set-status", description="Change a Registry status.")
    @app_commands.choices(status=STATUS_CHOICES)
    async def set_status(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        status: app_commands.Choice[str],
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                entry = registry.set_status(
                    connection,
                    guild_id=guild_id,
                    user_id=user.id,
                    status=status.value,
                    actor_user_id=interaction.user.id,
                )
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"`{entry.display_mark}` now has status **{entry.status}**.",
            ephemeral=True,
        )

    @app_commands.command(name="set-channel", description="Set the public Registry channel.")
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                registry.set_public_channel(
                    connection,
                    guild_id=guild_id,
                    channel_id=channel.id,
                    actor_user_id=interaction.user.id,
                )
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Public Registry notices will be posted in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="publish", description="Publish a member's public Registry card.")
    async def publish(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_path(self.bot))
        try:
            with managed_connection(_path(self.bot)) as connection:
                entry = registry.get_entry(connection, guild_id=guild_id, user_id=user.id)
                settings = registry.get_settings(connection, guild_id)
        except registry.RegistryError as exc:
            await interaction.response.send_message(f"Registry error: {exc}", ephemeral=True)
            return
        target = channel
        if target is None and settings and settings.public_channel_id:
            candidate = self.bot.get_channel(settings.public_channel_id)
            target = candidate if isinstance(candidate, discord.TextChannel) else None
        if target is None:
            await interaction.response.send_message("Set or provide a Registry channel.", ephemeral=True)
            return
        assert entry is not None
        await target.send(embed=views.public_card(entry))
        await interaction.response.send_message(
            f"Published `{entry.display_mark}` to {target.mention}.",
            ephemeral=True,
        )
