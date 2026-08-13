from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import discord
from discord.ext import commands, tasks

from services import ai, memory_extraction, memory_extraction_provider, memory_ledger, memory_policy
from services import member_profiles
from services.database import initialize_database, managed_connection, utc_now_iso

logger = logging.getLogger("wilhelmina.memory.events")
MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    guild_id: int | None = None
    source_context: str | None = None
    reason: str = ""


def _database_path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def _reply_targets_bot(message: discord.Message, bot_user_id: int) -> bool:
    reference = message.reference
    if reference is None:
        return False
    resolved = reference.resolved
    return isinstance(resolved, discord.Message) and resolved.author.id == int(bot_user_id)


def _mentions_bot(message: discord.Message, bot_user_id: int) -> bool:
    return any(user.id == int(bot_user_id) for user in message.mentions)


def _mentioned_member_ids(content: str, *, bot_user_id: int) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                int(match)
                for match in MENTION_PATTERN.findall(content)
                if int(match) != int(bot_user_id)
            }
        )
    )


class MemoryExtraction(commands.Cog):
    """Interaction-scoped automatic Memory Ledger ingestion."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.worker.start()

    def cog_unload(self) -> None:
        self.worker.cancel()

    async def _eligibility(self, message: discord.Message) -> Eligibility:
        if self.bot.user is None:
            return Eligibility(False, reason="bot_not_ready")
        if message.author.bot or message.webhook_id is not None:
            return Eligibility(False, reason="non_human")
        if not str(message.content or "").strip():
            return Eligibility(False, reason="no_text")

        home_guild_id = getattr(self.bot.settings, "home_guild_id", None)
        if home_guild_id is None:
            return Eligibility(False, reason="home_guild_unset")
        home_guild_id = int(home_guild_id)

        try:
            runtime = memory_policy.MemoryRuntimePolicy.from_env()
        except memory_policy.MemoryPolicyConfigurationError:
            return Eligibility(False, reason="invalid_runtime_policy")
        if not runtime.interaction_collection_enabled:
            return Eligibility(False, reason="runtime_off")

        is_dm = message.guild is None
        if not is_dm and message.guild.id != home_guild_id:
            return Eligibility(False, reason="wrong_guild")

        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            settings = memory_ledger.get_or_create_settings(connection, home_guild_id)
            if not settings.collection_enabled:
                return Eligibility(False, reason="persistent_pause")
            if not member_profiles.profile_has_current_consent(
                connection,
                guild_id=home_guild_id,
                user_id=message.author.id,
            ):
                return Eligibility(False, reason="consent_missing")

        if is_dm:
            return Eligibility(True, home_guild_id, "dm", "dm")

        assert message.guild is not None
        designated = settings.wilhelmina_channel_id == message.channel.id
        mentioned = _mentions_bot(message, self.bot.user.id)
        replied = _reply_targets_bot(message, self.bot.user.id)
        if not (designated or mentioned or replied):
            return Eligibility(False, reason="not_interaction")
        return Eligibility(True, home_guild_id, "guild", "interaction")

    async def _enqueue(self, message: discord.Message, *, edited: bool = False) -> None:
        eligibility = await self._eligibility(message)
        if not eligibility.eligible:
            return
        if not memory_extraction_provider.provider_ready():
            logger.info(
                "memory_extraction_skipped reason=provider_not_ready guild_id=%s message_id=%s",
                eligibility.guild_id,
                message.id,
            )
            return

        assert eligibility.guild_id is not None
        assert eligibility.source_context is not None
        content = str(message.content or "")
        edited_at = (
            message.edited_at.isoformat(timespec="seconds")
            if edited and message.edited_at is not None
            else None
        )
        try:
            initialize_database(_database_path(self.bot))
            with managed_connection(_database_path(self.bot)) as connection:
                if edited:
                    memory_extraction.mark_source_edited(
                        connection,
                        guild_id=eligibility.guild_id,
                        message_id=message.id,
                        edited_excerpt=content,
                        edited_at=edited_at or utc_now_iso(),
                    )
                memory_extraction.enqueue_message(
                    connection,
                    guild_id=eligibility.guild_id,
                    subject_user_id=message.author.id,
                    source_context=eligibility.source_context,
                    author_user_id=message.author.id,
                    channel_id=message.channel.id if eligibility.source_context == "guild" else None,
                    message_id=message.id,
                    jump_url=message.jump_url if eligibility.source_context == "guild" else None,
                    content=content,
                    source_created_at=message.created_at.isoformat(timespec="seconds"),
                    source_edited_at=edited_at,
                )
        except memory_ledger.BlockedMemoryContent:
            logger.info(
                "memory_extraction_rejected reason=sensitive_guard guild_id=%s message_id=%s",
                eligibility.guild_id,
                message.id,
            )
        except Exception as exc:
            logger.warning(
                "memory_extraction_enqueue_failed guild_id=%s message_id=%s exception=%s",
                eligibility.guild_id,
                message.id,
                type(exc).__name__,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._enqueue(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.content == after.content:
            return
        await self._enqueue(after, edited=True)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        home_guild_id = getattr(self.bot.settings, "home_guild_id", None)
        if home_guild_id is None:
            return
        if payload.guild_id is not None and int(payload.guild_id) != int(home_guild_id):
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            memory_extraction.mark_source_deleted(
                connection,
                guild_id=int(home_guild_id),
                message_id=payload.message_id,
            )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self,
        payload: discord.RawBulkMessageDeleteEvent,
    ) -> None:
        home_guild_id = getattr(self.bot.settings, "home_guild_id", None)
        if home_guild_id is None:
            return
        if payload.guild_id is not None and int(payload.guild_id) != int(home_guild_id):
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            for message_id in payload.message_ids:
                memory_extraction.mark_source_deleted(
                    connection,
                    guild_id=int(home_guild_id),
                    message_id=message_id,
                )

    @tasks.loop(seconds=2.0)
    async def worker(self) -> None:
        if self.bot.user is None or not memory_extraction_provider.provider_ready():
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            job = memory_extraction.claim_next_job(connection)
        if job is None or not job.content:
            return

        mentioned_ids = _mentioned_member_ids(job.content, bot_user_id=self.bot.user.id)
        provider_input = memory_extraction.build_provider_input(
            job,
            mentioned_members=[(user_id, str(user_id)) for user_id in mentioned_ids],
        )
        try:
            result = await memory_extraction_provider.extract_structured(
                instructions=memory_extraction.EXTRACTION_INSTRUCTIONS,
                input_text=provider_input,
                schema_name="wilhelmina_memory_proposal",
                schema=memory_extraction.EXTRACTION_SCHEMA,
            )
        except ai.AIPrivacyConfigurationError:
            result = None

        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            current = memory_extraction.get_job(connection, job.id)
            if (
                current is None
                or current.content_hash != job.content_hash
                or current.status != "processing"
            ):
                return
            if result is None:
                memory_extraction.mark_job_retry(
                    connection,
                    current,
                    error_code="provider_unavailable",
                )
                return
            try:
                proposal = memory_extraction.parse_proposal(
                    result.payload,
                    mentioned_member_ids=mentioned_ids,
                )
                memory_extraction.apply_proposal(
                    connection,
                    job=current,
                    proposal=proposal,
                    actor_user_id=self.bot.user.id,
                )
            except (memory_extraction.InvalidProposal, memory_ledger.BlockedMemoryContent):
                memory_extraction.mark_job_rejected(
                    connection,
                    current.id,
                    reason="invalid_proposal",
                )
                return
            except Exception as exc:
                logger.warning(
                    "memory_extraction_apply_failed job_id=%s exception=%s",
                    current.id,
                    type(exc).__name__,
                )
                memory_extraction.mark_job_retry(
                    connection,
                    current,
                    error_code="apply_failed",
                )
                return
            memory_extraction.mark_job_completed(connection, current.id)

    @worker.before_loop
    async def before_worker(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    initialize_database(_database_path(bot))
    with managed_connection(_database_path(bot)) as connection:
        memory_extraction.initialize_extraction_schema(connection)
    await bot.add_cog(MemoryExtraction(bot))
