from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from services import chat, chat_response, memory_context, memory_ledger, member_profiles, persona
from services.database import initialize_database, managed_connection

logger = logging.getLogger("wilhelmina.chat.events")


def _database_path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def _reply_author_user_id(message: discord.Message) -> int | None:
    reference = message.reference
    if reference is None:
        return None
    resolved = reference.resolved
    if isinstance(resolved, discord.Message):
        return int(resolved.author.id)
    return None


def _message_envelope(message: discord.Message) -> chat.ChatMessageEnvelope:
    return chat.ChatMessageEnvelope(
        message_id=int(message.id),
        author_user_id=int(message.author.id),
        author_is_bot=bool(message.author.bot),
        webhook_id=None if message.webhook_id is None else int(message.webhook_id),
        content=str(message.content or ""),
        guild_id=None if message.guild is None else int(message.guild.id),
        channel_id=int(message.channel.id),
        mentioned_user_ids=tuple(int(user.id) for user in message.mentions),
        reply_author_user_id=_reply_author_user_id(message),
    )


class Chat(commands.Cog):
    """Memory-aware direct-interaction chat for the approved Phase-6 surfaces."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if self.bot.user is None:
            return

        home_guild_id = getattr(self.bot.settings, "home_guild_id", None)
        if home_guild_id is None:
            return
        home_guild_id = int(home_guild_id)

        envelope = _message_envelope(message)
        if envelope.guild_id is not None and envelope.guild_id != home_guild_id:
            return

        path = _database_path(self.bot)
        try:
            initialize_database(path)
            with managed_connection(path) as connection:
                ledger_settings = memory_ledger.get_or_create_settings(
                    connection,
                    home_guild_id,
                )
                route = chat.route_chat_message(
                    envelope,
                    home_guild_id=home_guild_id,
                    bot_user_id=int(self.bot.user.id),
                    designated_channel_id=ledger_settings.wilhelmina_channel_id,
                    command_prefix=str(self.bot.command_prefix or "!"),
                )
                if not route.eligible:
                    return

                referenced_member_ids = chat.resolve_referenced_member_ids(
                    connection,
                    guild_id=home_guild_id,
                    interlocutor_user_id=envelope.author_user_id,
                    bot_user_id=int(self.bot.user.id),
                    content=envelope.content,
                    mentioned_user_ids=envelope.mentioned_user_ids,
                    reply_author_user_id=envelope.reply_author_user_id,
                )
                bundle = chat.assemble_chat_memory_context(
                    connection,
                    route=route,
                    interlocutor_user_id=envelope.author_user_id,
                    query=envelope.content,
                    referenced_member_ids=referenced_member_ids,
                )
        except member_profiles.MemberIdentityProfileNotFound:
            logger.info(
                "chat_routing_skipped reason=profile_missing guild_id=%s message_id=%s author_user_id=%s",
                home_guild_id,
                envelope.message_id,
                envelope.author_user_id,
            )
            return
        except (chat.ChatContractError, memory_context.MemoryContextError):
            logger.warning(
                "chat_routing_skipped reason=context_contract guild_id=%s message_id=%s "
                "author_user_id=%s",
                home_guild_id,
                envelope.message_id,
                envelope.author_user_id,
            )
            return
        except Exception as exc:
            logger.warning(
                "chat_routing_failed guild_id=%s message_id=%s author_user_id=%s exception=%s",
                home_guild_id,
                envelope.message_id,
                envelope.author_user_id,
                type(exc).__name__,
            )
            return

        assert route.surface is not None
        assert route.audience_scope is not None
        logger.info(
            "chat_context_prepared guild_id=%s message_id=%s author_user_id=%s surface=%s "
            "audience=%s referenced_count=%s speaker_memory_count=%s contextual_memory_count=%s",
            home_guild_id,
            envelope.message_id,
            envelope.author_user_id,
            route.surface.value,
            route.audience_scope.value,
            len(referenced_member_ids),
            len(bundle.speaker_profile),
            len(bundle.contextual_memories),
        )

        try:
            reply = await chat_response.generate_chat_reply_async(
                route=route,
                bundle=bundle,
                current_message=envelope.content,
            )
        except Exception as exc:
            logger.warning(
                "chat_generation_failed guild_id=%s message_id=%s author_user_id=%s exception=%s",
                home_guild_id,
                envelope.message_id,
                envelope.author_user_id,
                type(exc).__name__,
            )
            reply = chat_response.ChatReply(
                text=persona.fallback_for("chat"),
                provider_used=False,
                fallback_reason="unexpected_generation_failure",
            )

        try:
            await message.reply(
                reply.text,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
                fail_if_not_exists=False,
            )
        except discord.HTTPException as exc:
            logger.warning(
                "chat_send_failed guild_id=%s message_id=%s author_user_id=%s exception=%s status=%s",
                home_guild_id,
                envelope.message_id,
                envelope.author_user_id,
                type(exc).__name__,
                getattr(exc, "status", None),
            )
            return

        logger.info(
            "chat_reply_sent guild_id=%s message_id=%s author_user_id=%s surface=%s audience=%s "
            "provider_used=%s model=%s request_id=%s fallback_reason=%s",
            home_guild_id,
            envelope.message_id,
            envelope.author_user_id,
            route.surface.value,
            route.audience_scope.value,
            reply.provider_used,
            reply.model,
            reply.request_id,
            reply.fallback_reason,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Chat(bot))
