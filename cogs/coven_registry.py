from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from cogs.coven_registry_admin import CovenRegistryAdmin
from services import coven_registry as registry
from services import coven_registry_views as views
from services.database import initialize_database, managed_connection

logger = logging.getLogger("wilhelmina.registry")
PAGE_SIZE = 10


def database_path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def home_guild_id(bot: commands.Bot) -> int | None:
    value = getattr(bot.settings, "home_guild_id", None)
    return int(value) if value is not None else None


def iso(value: object | None) -> str | None:
    method = getattr(value, "isoformat", None)
    return str(method()) if callable(method) else (str(value) if value is not None else None)


async def guard_home(interaction: discord.Interaction, bot: commands.Bot) -> int | None:
    expected = home_guild_id(bot)
    if expected is None or interaction.guild_id != expected:
        await interaction.response.send_message(
            "The Coven Registry only opens inside Wilhelmina's configured home guild.",
            ephemeral=True,
        )
        return None
    return expected


@app_commands.guild_only()
class CovenRegistry(commands.GroupCog, group_name="registry"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="index", description="Open the public Coven Registry index.")
    async def index(
        self,
        interaction: discord.Interaction,
        page: app_commands.Range[int, 1, 999] = 1,
    ) -> None:
        guild_id = await guard_home(interaction, self.bot)
        if guild_id is None:
            return
        initialize_database(database_path(self.bot))
        with managed_connection(database_path(self.bot)) as connection:
            total = registry.count_entries(connection, guild_id=guild_id)
            pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            page = min(int(page), pages)
            entries = registry.list_entries(
                connection,
                guild_id=guild_id,
                limit=PAGE_SIZE,
                offset=(page - 1) * PAGE_SIZE,
            )
        await interaction.response.send_message(
            embed=views.index_card(entries, page=page, pages=pages, total=total)
        )

    @app_commands.command(name="me", description="Show your public Coven Registry card.")
    async def me(self, interaction: discord.Interaction) -> None:
        guild_id = await guard_home(interaction, self.bot)
        if guild_id is None:
            return
        initialize_database(database_path(self.bot))
        with managed_connection(database_path(self.bot)) as connection:
            entry = registry.get_entry(
                connection,
                guild_id=guild_id,
                user_id=interaction.user.id,
                required=False,
            )
        if entry is None:
            await interaction.response.send_message(
                "You are not recorded in the Coven Registry yet.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(embed=views.public_card(entry), ephemeral=True)


class CovenRegistryEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_home_member(self, member: discord.Member) -> bool:
        return home_guild_id(self.bot) == member.guild.id

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot or not self.is_home_member(member):
            return
        initialize_database(database_path(self.bot))
        try:
            with managed_connection(database_path(self.bot)) as connection:
                registry.register_pending_member(
                    connection,
                    guild_id=member.guild.id,
                    user_id=member.id,
                    display_name=member.display_name,
                    joined_at=iso(member.joined_at),
                    actor_user_id=member.id,
                )
        except registry.RegistryNotBootstrapped:
            logger.warning(
                "registry_join_skipped_unbootstrapped guild_id=%s user_id=%s",
                member.guild.id,
                member.id,
            )
        except Exception:
            logger.exception(
                "registry_join_failed guild_id=%s user_id=%s",
                member.guild.id,
                member.id,
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot or not self.is_home_member(member):
            return
        initialize_database(database_path(self.bot))
        try:
            actor = self.bot.user.id if self.bot.user else member.id
            with managed_connection(database_path(self.bot)) as connection:
                registry.archive_member(
                    connection,
                    guild_id=member.guild.id,
                    user_id=member.id,
                    actor_user_id=actor,
                )
        except Exception:
            logger.exception(
                "registry_archive_failed guild_id=%s user_id=%s",
                member.guild.id,
                member.id,
            )

    async def induct_from_covenant(
        self,
        *,
        member: discord.Member,
        rules_version_id: int,
        accepted_at: str,
    ) -> registry.InductionResult | None:
        if member.bot or not self.is_home_member(member):
            return None
        initialize_database(database_path(self.bot))
        try:
            with managed_connection(database_path(self.bot)) as connection:
                if registry.get_entry(
                    connection,
                    guild_id=member.guild.id,
                    user_id=member.id,
                    required=False,
                ) is None:
                    registry.register_pending_member(
                        connection,
                        guild_id=member.guild.id,
                        user_id=member.id,
                        display_name=member.display_name,
                        joined_at=iso(member.joined_at),
                        actor_user_id=member.id,
                    )
                result = registry.induct_member(
                    connection,
                    guild_id=member.guild.id,
                    user_id=member.id,
                    covenant_version_id=rules_version_id,
                    accepted_at=accepted_at,
                    actor_user_id=member.id,
                )
                settings = registry.get_settings(connection, member.guild.id)
        except registry.RegistryNotBootstrapped:
            logger.warning(
                "registry_induction_skipped_unbootstrapped guild_id=%s user_id=%s",
                member.guild.id,
                member.id,
            )
            return None
        if not result.notice_required or settings is None or settings.public_channel_id is None:
            return result
        channel = self.bot.get_channel(settings.public_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return result
        message = await channel.send(embed=views.induction_card(member, result.entry))
        with managed_connection(database_path(self.bot)) as connection:
            registry.mark_induction_notice_published(
                connection,
                guild_id=member.guild.id,
                user_id=member.id,
                message_id=message.id,
            )
        return result


def _install_rules_bridge(bot: commands.Bot, events: CovenRegistryEvents) -> None:
    """Bridge Covenant Gate acceptance without coupling its cog to Registry internals."""

    from services import rules as rules_service

    current = rules_service.accept_rules_version
    if getattr(current, "__registry_bridge__", False):
        return

    def bridged_accept_rules_version(*args, **kwargs):
        result = current(*args, **kwargs)
        guild_id = int(kwargs["guild_id"])
        user_id = int(kwargs["user_id"])
        guild = bot.get_guild(guild_id)
        member = guild.get_member(user_id) if guild else None
        if member is not None:
            bot.loop.create_task(
                events.induct_from_covenant(
                    member=member,
                    rules_version_id=result.acceptance.rules_version_id,
                    accepted_at=result.acceptance.accepted_at,
                )
            )
        return result

    bridged_accept_rules_version.__registry_bridge__ = True
    rules_service.accept_rules_version = bridged_accept_rules_version


async def setup(bot: commands.Bot) -> None:
    events = CovenRegistryEvents(bot)
    await bot.add_cog(CovenRegistry(bot))
    await bot.add_cog(CovenRegistryAdmin(bot))
    await bot.add_cog(events)
    _install_rules_bridge(bot, events)
