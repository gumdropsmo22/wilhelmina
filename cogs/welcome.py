from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from services.database import initialize_database, managed_connection
from services.guild_config import get_guild_config
from services.persona import fallback_for
from services.welcome import build_welcome_text, format_welcome_message

logger = logging.getLogger("wilhelmina.welcome")


def database_path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def home_guild_id(bot: commands.Bot) -> int | None:
    value = getattr(bot.settings, "home_guild_id", None)
    return int(value) if value is not None else None


class WelcomeCog(commands.Cog):
    """Post one configured-channel Wilhelmina greeting when a human joins the home guild."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot or home_guild_id(self.bot) != member.guild.id:
            return

        initialize_database(database_path(self.bot))
        with managed_connection(database_path(self.bot)) as connection:
            config = get_guild_config(connection, member.guild.id)

        if config is None or config.welcome_channel_id is None:
            logger.info(
                "welcome_skipped_unconfigured guild_id=%s user_id=%s",
                member.guild.id,
                member.id,
            )
            return

        channel = self.bot.get_channel(config.welcome_channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "welcome_skipped_invalid_channel guild_id=%s user_id=%s channel_id=%s",
                member.guild.id,
                member.id,
                config.welcome_channel_id,
            )
            return

        try:
            text = await build_welcome_text(display_name=member.display_name)
        except Exception:
            logger.exception(
                "welcome_persona_failed guild_id=%s user_id=%s",
                member.guild.id,
                member.id,
            )
            text = fallback_for("welcome")

        message = format_welcome_message(member_mention=member.mention, text=text)
        try:
            await channel.send(
                message,
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    roles=False,
                    users=[member],
                    replied_user=False,
                ),
            )
        except Exception:
            logger.exception(
                "welcome_send_failed guild_id=%s user_id=%s channel_id=%s",
                member.guild.id,
                member.id,
                config.welcome_channel_id,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
