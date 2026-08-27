from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from services import coven_registry as registry
from services import guild_config
from services import member_profiles
from services import rules as rules_service
from services.database import initialize_database, managed_connection
from services.member_identity import MemberIdentityError

logger = logging.getLogger("wilhelmina.identity")
STALE_COVENANT = "This covenant is outdated. Use `/rules` for the current one."


def _database_path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def _home_guild_id(bot: commands.Bot) -> int | None:
    value = getattr(bot.settings, "home_guild_id", None)
    return int(value) if value is not None else None


def _guild_today(connection, guild_id: int):
    config = guild_config.ensure_guild_config(connection, guild_id)
    return datetime.now(ZoneInfo(config.timezone)).date()


def _ensure_registry_entry(connection, member: discord.Member) -> registry.RegistryEntry:
    existing = registry.get_entry(
        connection,
        guild_id=member.guild.id,
        user_id=member.id,
        required=False,
    )
    if existing is not None:
        return existing
    result = registry.register_pending_member(
        connection,
        guild_id=member.guild.id,
        user_id=member.id,
        display_name=member.display_name,
        joined_at=member.joined_at.isoformat() if member.joined_at else None,
        actor_user_id=member.id,
    )
    return result.entry


def _is_private_identity_admin(interaction: discord.Interaction, bot: commands.Bot) -> bool:
    if interaction.guild_id is None or interaction.guild_id != _home_guild_id(bot):
        return False
    if not isinstance(interaction.user, discord.Member):
        return False
    if interaction.user.guild_permissions.manage_guild:
        return True
    initialize_database(_database_path(bot))
    with managed_connection(_database_path(bot)) as connection:
        settings = registry.get_settings(connection, interaction.guild_id)
    return settings is not None and settings.founder_user_id == interaction.user.id


class MemberInductionModal(discord.ui.Modal, title="Private member identity"):
    preferred_name = discord.ui.TextInput(
        label="What should Wilhelmina call you?",
        placeholder="The name you actually want used",
        required=True,
        max_length=80,
    )
    birth_date = discord.ui.TextInput(
        label="Full birth date",
        placeholder="YYYY-MM-DD",
        required=True,
        min_length=10,
        max_length=10,
    )

    def __init__(self, *, bot: commands.Bot, guild_id: int, rules_version_id: int) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.guild_id = int(guild_id)
        self.rules_version_id = int(rules_version_id)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Finish induction inside Wilhelmina's configured server.",
                ephemeral=True,
            )
            return
        if self.guild_id != _home_guild_id(self.bot):
            await interaction.response.send_message(
                "This induction belongs to a different server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                rules = rules_service.get_rules_version_by_id(connection, self.rules_version_id)
                if not rules.is_active or rules.guild_id != self.guild_id:
                    await interaction.followup.send(STALE_COVENANT, ephemeral=True)
                    return

                _ensure_registry_entry(connection, interaction.user)
                member_profiles.save_member_identity(
                    connection,
                    guild_id=self.guild_id,
                    user_id=interaction.user.id,
                    discord_display_name=interaction.user.display_name,
                    preferred_name=str(self.preferred_name.value),
                    birth_date=str(self.birth_date.value),
                    today=_guild_today(connection, self.guild_id),
                    actor_user_id=interaction.user.id,
                )
                acceptance = rules_service.accept_rules_version(
                    connection,
                    guild_id=self.guild_id,
                    user_id=interaction.user.id,
                    rules_version_id=rules.id,
                    accepted_via="button+identity",
                    actor_user_id=interaction.user.id,
                )
        except (MemberIdentityError, rules_service.RulesError, registry.RegistryError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception(
                "identity_induction_failed guild_id=%s user_id=%s",
                self.guild_id,
                interaction.user.id,
            )
            await interaction.followup.send(
                "Induction hit a technical failure. Nothing half-recorded was kept.",
                ephemeral=True,
            )
            return

        if acceptance.already_accepted:
            message = "Your private identity profile is recorded; that covenant was already accepted."
        else:
            message = "Induction complete. I have both names and your full birthday."
        await interaction.followup.send(message, ephemeral=True)


async def begin_covenant_acceptance(
    interaction: discord.Interaction,
    *,
    bot: commands.Bot,
    guild_id: int,
    rules_version_id: int,
) -> None:
    """Accept directly when the private identity profile already exists."""

    initialize_database(_database_path(bot))
    with managed_connection(_database_path(bot)) as connection:
        rules = rules_service.get_rules_version_by_id(connection, rules_version_id)
        if not rules.is_active or rules.guild_id != int(guild_id):
            await interaction.response.send_message(STALE_COVENANT, ephemeral=True)
            return
        profile = member_profiles.get_member_identity(
            connection,
            guild_id=int(guild_id),
            user_id=interaction.user.id,
            required=False,
        )
        if profile is not None:
            result = rules_service.accept_rules_version(
                connection,
                guild_id=int(guild_id),
                user_id=interaction.user.id,
                rules_version_id=rules.id,
                accepted_via="button",
                actor_user_id=interaction.user.id,
            )
            message = (
                "Already accepted. The ledger did not forget you."
                if result.already_accepted
                else "Recorded. You accepted the covenant."
            )
            await interaction.response.send_message(message, ephemeral=True)
            return

    await interaction.response.send_modal(
        MemberInductionModal(
            bot=bot,
            guild_id=guild_id,
            rules_version_id=rules_version_id,
        )
    )


class MemberIdentityEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if after.bot or after.guild.id != _home_guild_id(self.bot):
            return
        if before.display_name == after.display_name:
            return

        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                if registry.get_entry(
                    connection,
                    guild_id=after.guild.id,
                    user_id=after.id,
                    required=False,
                ) is None:
                    return
                member_profiles.refresh_discord_display_name(
                    connection,
                    guild_id=after.guild.id,
                    user_id=after.id,
                    discord_display_name=after.display_name,
                    actor_user_id=self.bot.user.id if self.bot.user else None,
                )
        except Exception:
            logger.exception(
                "identity_display_name_refresh_failed guild_id=%s user_id=%s",
                after.guild.id,
                after.id,
            )


@app_commands.guild_only()
class MemberIdentityAdmin(commands.GroupCog, group_name="identity-admin"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if _is_private_identity_admin(interaction, self.bot):
            return True
        await interaction.response.send_message(
            "That identity file is founder/admin only.",
            ephemeral=True,
        )
        return False

    @app_commands.command(name="show", description="Privately inspect one member identity profile.")
    async def show(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not await self._guard(interaction):
            return

        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            profile = member_profiles.get_member_identity(
                connection,
                guild_id=interaction.guild_id,
                user_id=member.id,
                required=False,
            )
            if profile is None:
                await interaction.response.send_message(
                    "That member has not completed the private identity profile.",
                    ephemeral=True,
                )
                return
            context = profile.trusted_chat_context(
                on_date=_guild_today(connection, interaction.guild_id)
            )

        await interaction.response.send_message(
            "**Private identity profile**\n"
            "```txt\n"
            f"discord_name = {context.discord_display_name}\n"
            f"preferred    = {context.preferred_name}\n"
            f"birth_date   = {context.birth_date}\n"
            f"age          = {context.age}\n"
            "```",
            ephemeral=True,
        )


async def install_member_identity(bot: commands.Bot) -> None:
    if bot.get_cog("MemberIdentityEvents") is None:
        await bot.add_cog(MemberIdentityEvents(bot))
    if bot.get_cog("MemberIdentityAdmin") is None:
        await bot.add_cog(MemberIdentityAdmin(bot))
