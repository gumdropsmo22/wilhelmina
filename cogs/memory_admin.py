from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from services import memory_admin as admin_service
from services import memory_ledger, memory_policy, member_profiles
from services.database import initialize_database, managed_connection

PAGE_SIZE = 8
DISCORD_EMBED_TEXT_LIMIT = 6000
RECEIPT_MESSAGE_TEXT_BUDGET = 5500
RECEIPT_FOOTER_RESERVE = 160
MAX_EMBEDS_PER_MESSAGE = 10
MAX_DISCORD_USER_ID = (1 << 64) - 1
CATEGORY_CHOICES = [
    app_commands.Choice(name=value, value=value) for value in memory_ledger.VALID_CATEGORIES
]
LABEL_CHOICES = [
    app_commands.Choice(name=value, value=value) for value in memory_ledger.VALID_LABELS
]
PRIVACY_CHOICES = [
    app_commands.Choice(name=value, value=value)
    for value in memory_ledger.VALID_PRIVACY_CLASSES
]
REVEAL_CHOICES = [
    app_commands.Choice(name=value, value=value) for value in memory_ledger.VALID_REVEAL_SCOPES
]
SEARCH_SCOPE_CHOICES = [
    app_commands.Choice(name="all admin-visible scopes", value="all"),
    *REVEAL_CHOICES,
]


def _database_path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def _short(value: str, *, limit: int = 280) -> str:
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _page(items: list, requested: int) -> tuple[list, int, int]:
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    current = min(max(1, int(requested)), pages)
    start = (current - 1) * PAGE_SIZE
    return items[start : start + PAGE_SIZE], current, pages


def _parse_user_id(value: str) -> int:
    cleaned = value.strip()
    if not cleaned.isdecimal():
        raise ValueError("Discord user ID must contain digits only")
    user_id = int(cleaned)
    if user_id <= 0 or user_id > MAX_DISCORD_USER_ID:
        raise ValueError("Discord user ID must be a positive 64-bit snowflake")
    return user_id


def _identity_state(identity) -> str:
    return "complete" if identity is not None else "none"


def _memory_line(memory: memory_ledger.MemoryRecord) -> str:
    qualifier = "Gossip" if memory.is_gossip else memory.epistemic_label
    return (
        f"**#{memory.id}** · `{memory.category}` · `{qualifier}` · "
        f"`{memory.privacy_class}/{memory.reveal_scope}` · imp `{memory.importance}`\n"
        f"{_short(memory.summary)}"
    )


def _memory_embed(memory: memory_ledger.MemoryRecord) -> discord.Embed:
    embed = discord.Embed(
        title=f"Memory #{memory.id}",
        description=_short(memory.summary, limit=3900),
    )
    embed.add_field(name="Subject", value=f"`{memory.subject_user_id}`", inline=True)
    embed.add_field(name="Category", value=memory.category, inline=True)
    embed.add_field(name="Label", value=memory.epistemic_label, inline=True)
    embed.add_field(name="Privacy", value=memory.privacy_class, inline=True)
    embed.add_field(name="Reveal scope", value=memory.reveal_scope, inline=True)
    embed.add_field(name="Importance", value=str(memory.importance), inline=True)
    embed.add_field(name="Topic", value=f"`{memory.topic_key}`", inline=False)
    embed.add_field(name="Created", value=memory.created_at, inline=False)
    embed.add_field(name="Updated", value=memory.updated_at, inline=False)
    if memory.is_gossip:
        embed.set_footer(text="Unverified gossip: attribution/evidence lives in receipts.")
    return embed


def _receipt_embed(receipt: memory_ledger.MemoryReceipt) -> discord.Embed:
    embed = discord.Embed(title=f"Receipt #{receipt.id} · memory #{receipt.memory_id}")
    embed.add_field(
        name="Source",
        value=f"{receipt.source_kind}/{receipt.source_context}",
        inline=True,
    )
    embed.add_field(name="Author", value=f"`{receipt.author_user_id}`", inline=True)
    embed.add_field(
        name="Message",
        value=f"`{receipt.message_id}`" if receipt.message_id else "admin",
        inline=True,
    )
    embed.add_field(
        name="Channel",
        value=f"`{receipt.channel_id}`" if receipt.channel_id else "—",
        inline=True,
    )
    embed.add_field(
        name="Source state",
        value=(
            "deleted"
            if receipt.source_deleted_at
            else ("edited" if receipt.edited_excerpt else "original")
        ),
        inline=True,
    )
    embed.add_field(name="Source created", value=receipt.source_created_at, inline=False)
    embed.add_field(
        name="Original excerpt",
        value=_short(receipt.original_excerpt, limit=1000),
        inline=False,
    )
    if receipt.edited_excerpt:
        embed.add_field(
            name="Latest edited excerpt",
            value=_short(receipt.edited_excerpt, limit=1000),
            inline=False,
        )
    if receipt.jump_url:
        embed.add_field(name="Jump", value=receipt.jump_url, inline=False)
    return embed


def _embed_text_size(embed: discord.Embed) -> int:
    """Return Discord's aggregate text contribution for one embed."""

    data = embed.to_dict()
    total = len(str(data.get("title", ""))) + len(str(data.get("description", "")))
    total += len(str(data.get("footer", {}).get("text", "")))
    total += len(str(data.get("author", {}).get("name", "")))
    for field in data.get("fields", []):
        total += len(str(field.get("name", "")))
        total += len(str(field.get("value", "")))
    return total


def _receipt_embed_groups(
    receipts: list[memory_ledger.MemoryReceipt],
    *,
    current_page: int,
    page_count: int,
    total_receipts: int,
) -> list[list[discord.Embed]]:
    """Render one logical receipt page into Discord-safe message groups."""

    embeds = [_receipt_embed(receipt) for receipt in receipts]
    if not embeds:
        return []

    payload_budget = RECEIPT_MESSAGE_TEXT_BUDGET - RECEIPT_FOOTER_RESERVE
    groups: list[list[discord.Embed]] = []
    current_group: list[discord.Embed] = []
    current_size = 0

    for embed in embeds:
        embed_size = _embed_text_size(embed)
        if embed_size > DISCORD_EMBED_TEXT_LIMIT:
            raise ValueError("A receipt embed exceeds Discord's individual 6,000-character limit")
        if embed_size > payload_budget:
            raise ValueError("A receipt embed is too large for the safe receipt message budget")

        would_overflow = current_group and (
            current_size + embed_size > payload_budget
            or len(current_group) >= MAX_EMBEDS_PER_MESSAGE
        )
        if would_overflow:
            groups.append(current_group)
            current_group = []
            current_size = 0

        current_group.append(embed)
        current_size += embed_size

    if current_group:
        groups.append(current_group)

    page_start = (current_page - 1) * PAGE_SIZE
    consumed = 0
    part_count = len(groups)
    for part_number, group in enumerate(groups, start=1):
        first_receipt = page_start + consumed + 1
        last_receipt = first_receipt + len(group) - 1
        group[-1].set_footer(
            text=(
                f"Page {current_page}/{page_count} · receipts "
                f"{first_receipt}-{last_receipt}/{total_receipts} · "
                f"part {part_number}/{part_count}"
            )
        )
        consumed += len(group)

        group_size = sum(_embed_text_size(embed) for embed in group)
        if group_size > RECEIPT_MESSAGE_TEXT_BUDGET:
            raise ValueError("Receipt embed group exceeds the safe Discord message budget")

    return groups


async def _send_receipt_embed_groups(
    interaction: discord.Interaction,
    groups: list[list[discord.Embed]],
) -> None:
    """Send the first receipt group as the response and overflow as private follow-ups."""

    await interaction.response.send_message(embeds=groups[0], ephemeral=True)
    for group in groups[1:]:
        await interaction.followup.send(embeds=group, ephemeral=True)


@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
class MemoryAdmin(commands.GroupCog, group_name="memory-admin"):
    """Founder/admin-only Memory Ledger controls. Every response is ephemeral."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _guard(self, interaction: discord.Interaction) -> int | None:
        permissions = getattr(interaction.user, "guild_permissions", None)
        expected = getattr(self.bot.settings, "home_guild_id", None)
        if not permissions or not permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return None
        if expected is None or interaction.guild_id != int(expected):
            await interaction.response.send_message(
                "Run this inside Wilhelmina's configured home guild.",
                ephemeral=True,
            )
            return None
        return int(expected)

    async def _ledger_error(self, interaction: discord.Interaction, exc: Exception) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(f"Memory Ledger error: {exc}", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Memory Ledger error: {exc}",
                ephemeral=True,
            )

    async def _send_member_data_summary(
        self,
        interaction: discord.Interaction,
        *,
        guild_id: int,
        user_id: int,
    ) -> None:
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            summary = admin_service.summarize_member(
                connection,
                guild_id=guild_id,
                subject_user_id=user_id,
            )
            identity = member_profiles.get_member_identity(
                connection,
                guild_id=guild_id,
                user_id=user_id,
                required=False,
            )
        await interaction.response.send_message(
            "**Member data summary**\n```txt\n"
            f"user_id                  = {user_id}\n"
            f"memory_count             = {summary.memory_count}\n"
            f"receipt_count_total      = {summary.receipt_count}\n"
            f"subject_receipts         = {summary.subject_receipt_count}\n"
            f"authored_on_other_people = {summary.authored_cross_subject_receipt_count}\n"
            f"gossip                   = {summary.gossip_count}\n"
            f"restricted               = {summary.restricted_count}\n"
            f"admin_only               = {summary.admin_only_count}\n"
            f"identity                 = {_identity_state(identity)}\n```\n"
            "`receipt_count_total` is de-duplicated by scope: receipts on this member's "
            "own memories plus receipts they authored on somebody else's memory. "
            "Use `/memory-admin profile` and `/memory-admin receipts` for private access review "
            "when the member is still selectable; use record IDs/search for archived evidence.",
            ephemeral=True,
        )

    async def _delete_member_data(
        self,
        interaction: discord.Interaction,
        *,
        guild_id: int,
        user_id: int,
        display: str,
    ) -> None:
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            result = admin_service.delete_member_data(
                connection,
                guild_id=guild_id,
                subject_user_id=user_id,
                actor_user_id=interaction.user.id,
            )
        await interaction.response.send_message(
            f"Memory Ledger purge complete for {display}: "
            f"**{result.subject_memory_count_deleted}** subject memory record(s), "
            f"**{result.authored_cross_subject_receipt_count_deleted}** receipt(s) authored "
            "on other members' memories, and "
            f"**{result.evidence_orphan_memory_count_deleted}** additional memory record(s) "
            "deleted because no evidence remained. "
            "Coven Registry and private identity records were not changed.",
            ephemeral=True,
        )

    @app_commands.command(
        name="status",
        description="Show private Memory Ledger controls and integrity status.",
    )
    async def status(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            summary = admin_service.summarize_ledger(connection, guild_id=guild_id)
        try:
            runtime = memory_policy.MemoryRuntimePolicy.from_env()
            runtime_mode = runtime.collection_mode
            interaction_gate = (
                "allowed" if runtime.interaction_collection_enabled else "blocked"
            )
            ambient_gate = "ready" if runtime.ambient_collection_ready else "blocked"
        except memory_policy.MemoryPolicyConfigurationError as exc:
            runtime_mode = f"INVALID ({exc})"
            interaction_gate = "blocked"
            ambient_gate = "blocked"

        settings = summary.settings
        channel = (
            f"<#{settings.wilhelmina_channel_id}> (`{settings.wilhelmina_channel_id}`)"
            if settings.wilhelmina_channel_id
            else "unset"
        )
        integrity = summary.integrity
        await interaction.response.send_message(
            "**Memory Ledger status**\n```txt\n"
            f"persistent_gate     = {'resumed' if settings.collection_enabled else 'paused'}\n"
            f"runtime_mode        = {runtime_mode}\n"
            f"interaction_policy  = {interaction_gate}\n"
            f"ambient_policy      = {ambient_gate}\n"
            f"records_total       = {summary.total_records}\n"
            f"records_active      = {summary.active_records}\n"
            f"subjects            = {summary.subject_count}\n"
            f"receipts            = {summary.receipt_count}\n"
            f"gossip              = {summary.gossip_records}\n"
            f"restricted          = {summary.restricted_records}\n"
            f"admin_only          = {summary.admin_only_records}\n"
            f"contradictions      = {summary.contradiction_count}\n"
            f"integrity           = {'ok' if integrity.ok else 'FAILED'}\n"
            f"foreign_key_errors  = {integrity.foreign_key_violations}\n"
            f"entity_errors       = {integrity.orphan_entities + integrity.missing_system_entities}\n"
            f"contradiction_errors= {integrity.bad_contradictions}\n"
            f"fts                 = {'ok' if integrity.fts_available else 'missing'}\n```\n"
            f"Designated Wilhelmina channel: {channel}\n"
            "Automatic extraction is controlled independently by the runtime feature/policy "
            "gates above; this command manages the persistent local gate.",
            ephemeral=True,
        )

    @app_commands.command(
        name="pause",
        description="Persistently pause Memory Ledger collection.",
    )
    async def pause(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            memory_ledger.set_collection_enabled(
                connection,
                guild_id=guild_id,
                enabled=False,
                actor_user_id=interaction.user.id,
            )
        await interaction.response.send_message(
            "Memory Ledger collection gate is **paused**. Existing memories stay intact.",
            ephemeral=True,
        )

    @app_commands.command(
        name="resume",
        description="Persistently resume the Memory Ledger collection gate.",
    )
    async def resume(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            memory_ledger.set_collection_enabled(
                connection,
                guild_id=guild_id,
                enabled=True,
                actor_user_id=interaction.user.id,
            )
        await interaction.response.send_message(
            "Memory Ledger collection gate is **resumed**. Runtime collection policy still "
            "applies independently.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set-channel",
        description="Set the designated memory-aware Wilhelmina channel.",
    )
    async def set_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            memory_ledger.set_wilhelmina_channel(
                connection,
                guild_id=guild_id,
                channel_id=channel.id,
                actor_user_id=interaction.user.id,
            )
        await interaction.response.send_message(
            f"Designated Wilhelmina channel set to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="clear-channel",
        description="Clear the designated memory-aware Wilhelmina channel.",
    )
    async def clear_channel(self, interaction: discord.Interaction) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            memory_ledger.set_wilhelmina_channel(
                connection,
                guild_id=guild_id,
                channel_id=None,
                actor_user_id=interaction.user.id,
            )
        await interaction.response.send_message(
            "Designated Wilhelmina channel cleared.",
            ephemeral=True,
        )

    @app_commands.command(
        name="profile",
        description="Open a member's private Memory Ledger profile.",
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        page: app_commands.Range[int, 1, 999] = 1,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            memories = memory_ledger.list_profile(
                connection,
                guild_id=guild_id,
                subject_user_id=user.id,
            )
            identity = member_profiles.get_member_identity(
                connection,
                guild_id=guild_id,
                user_id=user.id,
                required=False,
            )
        rows, current, pages = _page(memories, int(page))
        embed = discord.Embed(
            title=f"Memory Ledger · {user.display_name}",
            description=(
                "\n\n".join(_memory_line(memory) for memory in rows)
                if rows
                else "No saved memories."
            ),
        )
        embed.add_field(name="Discord user ID", value=f"`{user.id}`", inline=False)
        if identity is not None:
            trusted = identity.trusted_chat_context(on_date=date.today())
            embed.add_field(name="Preferred name", value=trusted.preferred_name, inline=True)
            embed.add_field(name="Birth date", value=trusted.birth_date, inline=True)
            embed.add_field(name="Age", value=str(trusted.age), inline=True)
        embed.set_footer(
            text=(
                f"Page {current}/{pages} · {len(memories)} active memories · "
                "private admin surface"
            )
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="show",
        description="Open one private Memory Ledger record by ID.",
    )
    async def show(
        self,
        interaction: discord.Interaction,
        memory_id: app_commands.Range[int, 1],
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                memory = memory_ledger.get_memory(connection, int(memory_id))
                if memory is None or memory.guild_id != guild_id:
                    raise memory_ledger.MemoryNotFound(
                        "No Memory Ledger record exists with that ID in this guild"
                    )
                receipts = memory_ledger.list_receipts(connection, memory.id)
                contradictions = memory_ledger.list_contradictions(
                    connection,
                    memory_id=memory.id,
                )
        except memory_ledger.MemoryLedgerError as exc:
            await self._ledger_error(interaction, exc)
            return
        embed = _memory_embed(memory)
        embed.add_field(name="Receipts", value=str(len(receipts)), inline=True)
        embed.add_field(name="Contradictions", value=str(len(contradictions)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="receipts",
        description="Open evidence receipts for one Memory Ledger record.",
    )
    async def receipts(
        self,
        interaction: discord.Interaction,
        memory_id: app_commands.Range[int, 1],
        page: app_commands.Range[int, 1, 999] = 1,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                memory = memory_ledger.get_memory(connection, int(memory_id))
                if memory is None or memory.guild_id != guild_id:
                    raise memory_ledger.MemoryNotFound(
                        "No Memory Ledger record exists with that ID in this guild"
                    )
                all_receipts = memory_ledger.list_receipts(connection, memory.id)
        except memory_ledger.MemoryLedgerError as exc:
            await self._ledger_error(interaction, exc)
            return
        rows, current, pages = _page(all_receipts, int(page))
        if not rows:
            await interaction.response.send_message(
                "That memory has no receipts.",
                ephemeral=True,
            )
            return
        try:
            groups = _receipt_embed_groups(
                rows,
                current_page=current,
                page_count=pages,
                total_receipts=len(all_receipts),
            )
        except ValueError as exc:
            await self._ledger_error(interaction, exc)
            return
        await _send_receipt_embed_groups(interaction, groups)

    @app_commands.command(
        name="search",
        description="Search private Memory Ledger records locally.",
    )
    @app_commands.choices(scope=SEARCH_SCOPE_CHOICES)
    async def search(
        self,
        interaction: discord.Interaction,
        query: str,
        user: discord.Member | None = None,
        scope: str = "all",
        page: app_commands.Range[int, 1, 12] = 1,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        reveal_scopes = (
            memory_ledger.VALID_REVEAL_SCOPES if scope == "all" else (scope,)
        )
        fetch_limit = min(100, max(PAGE_SIZE, int(page) * PAGE_SIZE))
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                hits = memory_ledger.search_memories(
                    connection,
                    guild_id=guild_id,
                    query=query,
                    reveal_scopes=reveal_scopes,
                    subject_user_ids=(user.id,) if user else None,
                    limit=fetch_limit,
                )
        except memory_ledger.MemoryLedgerError as exc:
            await self._ledger_error(interaction, exc)
            return
        start = (int(page) - 1) * PAGE_SIZE
        rows = hits[start : start + PAGE_SIZE]
        if not rows:
            await interaction.response.send_message(
                "No matching Memory Ledger records on that page.",
                ephemeral=True,
            )
            return
        description = "\n\n".join(_memory_line(hit.memory) for hit in rows)
        embed = discord.Embed(
            title=f"Memory search · {_short(query, limit=80)}",
            description=description,
        )
        embed.set_footer(text=f"Page {int(page)} · local FTS · private admin surface")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="add",
        description="Manually add an admin-authored Memory Ledger record.",
    )
    @app_commands.choices(
        category=CATEGORY_CHOICES,
        label=LABEL_CHOICES,
        privacy=PRIVACY_CHOICES,
        scope=REVEAL_CHOICES,
    )
    async def add(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        category: str,
        label: str,
        summary: str,
        topic: str | None = None,
        privacy: str = "ordinary",
        scope: str = "cross_member",
        importance: app_commands.Range[int, 0, 100] = 50,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                result, stored = admin_service.add_admin_memory(
                    connection,
                    guild_id=guild_id,
                    subject_user_id=user.id,
                    category=category,
                    epistemic_label=label,
                    summary=summary,
                    topic_key=topic,
                    actor_user_id=interaction.user.id,
                    privacy_class=privacy,
                    reveal_scope=scope,
                    importance=int(importance),
                )
        except (memory_ledger.MemoryLedgerError, sqlite3.IntegrityError) as exc:
            await self._ledger_error(interaction, exc)
            return
        verb = "created" if result.created else "confirmed existing"
        suffix = (
            f" Replaced same-topic memory IDs: {', '.join(map(str, result.replaced_memory_ids))}."
            if result.replaced_memory_ids
            else ""
        )
        duplicate_note = (
            " Duplicate confirmation merged its receipt; existing privacy/reveal/importance "
            "metadata was not changed. Use `/memory-admin edit` to change metadata explicitly."
            if not result.created
            else ""
        )
        await interaction.response.send_message(
            f"Memory **#{stored.id}** {verb} for {user.mention}.{suffix}{duplicate_note} "
            f"Stored metadata: `{stored.privacy_class}/{stored.reveal_scope}` · "
            f"importance `{stored.importance}`.",
            ephemeral=True,
        )

    @app_commands.command(
        name="edit",
        description="Edit one Memory Ledger record deterministically.",
    )
    async def edit(
        self,
        interaction: discord.Interaction,
        memory_id: app_commands.Range[int, 1],
        summary: str | None = None,
        category: str | None = None,
        label: str | None = None,
        topic: str | None = None,
        privacy: str | None = None,
        scope: str | None = None,
        importance: int | None = None,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        if all(
            value is None
            for value in (summary, category, label, topic, privacy, scope, importance)
        ):
            await interaction.response.send_message(
                "Give me at least one field to change.",
                ephemeral=True,
            )
            return
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                existing = memory_ledger.get_memory(connection, int(memory_id))
                if existing is None or existing.guild_id != guild_id:
                    raise memory_ledger.MemoryNotFound(
                        "No Memory Ledger record exists with that ID in this guild"
                    )
                updated = memory_ledger.update_memory(
                    connection,
                    memory_id=int(memory_id),
                    actor_user_id=interaction.user.id,
                    summary=summary,
                    category=category,
                    epistemic_label=label,
                    topic_key=topic,
                    privacy_class=privacy,
                    reveal_scope=scope,
                    importance=importance,
                )
        except (memory_ledger.MemoryLedgerError, sqlite3.IntegrityError) as exc:
            await self._ledger_error(interaction, exc)
            return
        await interaction.response.send_message(embed=_memory_embed(updated), ephemeral=True)

    @app_commands.command(
        name="delete",
        description="Permanently delete one memory and every receipt.",
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        memory_id: app_commands.Range[int, 1],
        confirmation: str,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        if confirmation != "DELETE":
            await interaction.response.send_message(
                "Destructive action refused. Type `DELETE` exactly in the confirmation field.",
                ephemeral=True,
            )
            return
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                memory = memory_ledger.get_memory(connection, int(memory_id))
                if memory is None or memory.guild_id != guild_id:
                    raise memory_ledger.MemoryNotFound(
                        "No Memory Ledger record exists with that ID in this guild"
                    )
                memory_ledger.delete_memory(
                    connection,
                    memory_id=int(memory_id),
                    actor_user_id=interaction.user.id,
                )
        except memory_ledger.MemoryLedgerError as exc:
            await self._ledger_error(interaction, exc)
            return
        await interaction.response.send_message(
            f"Memory **#{int(memory_id)}** and its dependent receipts/index rows were "
            "permanently deleted.",
            ephemeral=True,
        )

    @app_commands.command(
        name="member-data",
        description="Show content-free counts for a current member data request.",
    )
    async def member_data(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        await self._send_member_data_summary(
            interaction,
            guild_id=guild_id,
            user_id=user.id,
        )

    @app_commands.command(
        name="member-data-id",
        description="Show content-free counts for a departed member by Discord user ID.",
    )
    async def member_data_id(
        self,
        interaction: discord.Interaction,
        user_id: str,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        try:
            parsed_user_id = _parse_user_id(user_id)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await self._send_member_data_summary(
            interaction,
            guild_id=guild_id,
            user_id=parsed_user_id,
        )

    @app_commands.command(
        name="delete-member",
        description="Permanently purge one current member's Memory Ledger data.",
    )
    async def delete_member(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        confirmation: str,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        if confirmation != "DELETE MEMBER":
            await interaction.response.send_message(
                "Destructive action refused. Type `DELETE MEMBER` exactly. This only "
                "purges Memory Ledger data, not Registry/identity records.",
                ephemeral=True,
            )
            return
        await self._delete_member_data(
            interaction,
            guild_id=guild_id,
            user_id=user.id,
            display=user.mention,
        )

    @app_commands.command(
        name="delete-member-id",
        description="Permanently purge a departed member's Memory Ledger data by user ID.",
    )
    async def delete_member_id(
        self,
        interaction: discord.Interaction,
        user_id: str,
        confirmation: str,
    ) -> None:
        guild_id = await self._guard(interaction)
        if guild_id is None:
            return
        try:
            parsed_user_id = _parse_user_id(user_id)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        if confirmation != "DELETE MEMBER":
            await interaction.response.send_message(
                "Destructive action refused. Type `DELETE MEMBER` exactly. This only "
                "purges Memory Ledger data, not Registry/identity records.",
                ephemeral=True,
            )
            return
        await self._delete_member_data(
            interaction,
            guild_id=guild_id,
            user_id=parsed_user_id,
            display=f"user ID `{parsed_user_id}`",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemoryAdmin(bot))
