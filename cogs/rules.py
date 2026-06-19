from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from services import rules as rules_service
from services.database import initialize_database, managed_connection
from services.persona import render_persona_text

RULES_FIELD_LIMIT = 900


def _database_path(bot: commands.Bot) -> Path:
    return Path(bot.settings.database_path)


def _home_guild_id(bot: commands.Bot) -> int | None:
    value = getattr(bot.settings, "home_guild_id", None)
    return int(value) if value is not None else None


async def _guard_home_guild(interaction: discord.Interaction, bot: commands.Bot) -> bool:
    home_guild_id = _home_guild_id(bot)
    if home_guild_id is None:
        await interaction.response.send_message(
            "Cannot resolve Wilhelmina's home guild. Set `HOME_GUILD_ID` first.",
            ephemeral=True,
        )
        return False
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "Run this command inside Wilhelmina's configured home guild.",
            ephemeral=True,
        )
        return False
    if int(interaction.guild_id) != home_guild_id:
        await interaction.response.send_message(
            "This rules panel only runs in Wilhelmina's configured home guild.",
            ephemeral=True,
        )
        return False
    return True


def _guild_id(interaction: discord.Interaction) -> int:
    if interaction.guild_id is None:
        raise RuntimeError("guild_id is unavailable after home-guild guard")
    return int(interaction.guild_id)


def _chunk_text(value: str) -> list[str]:
    text = value.strip() or "No rules text has been written yet."
    return [text[index : index + RULES_FIELD_LIMIT] for index in range(0, len(text), RULES_FIELD_LIMIT)]


async def build_rules_embed(
    *,
    interaction: discord.Interaction,
    rules: rules_service.RulesVersion,
    mode: str,
) -> discord.Embed:
    intro = await render_persona_text(
        feature_key="rules_intro",
        task=(
            "Write one ceremonial introduction line for a Discord rules covenant. "
            "Do not add, remove, reinterpret, or summarize rules."
        ),
        context={
            "guild": interaction.guild.name if interaction.guild else "unknown guild",
            "mode": mode,
            "version": rules.version_tag,
            "stored_intro": rules.intro_text,
        },
        fallback=rules.intro_text,
    )
    embed = discord.Embed(title=rules.title, description=intro, color=0x6E00FF)
    embed.set_author(name="WILHELMINA • COVENANT GATE", icon_url="cdn/witch-sigil.png")
    for index, chunk in enumerate(_chunk_text(rules.body_text), start=1):
        embed.add_field(name=f"Rules {index}", value=chunk, inline=False)
    embed.set_footer(text=f"Rules version: {rules.version_tag} • haunt://coven/rules")
    return embed


class CovenantGateView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: commands.Bot,
        guild_id: int,
        rules_version_id: int,
        accept_label: str,
        author_id: int | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(timeout=None if persistent else 600)
        self.bot = bot
        self.guild_id = int(guild_id)
        self.rules_version_id = int(rules_version_id)
        self.author_id = int(author_id) if author_id is not None else None
        self.accept_button.custom_id = f"wilhelmina:rules_accept:{guild_id}:{rules_version_id}"
        self.accept_button.label = accept_label[:80]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id is None or interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "This panel was opened for another user. Use `/rules` to open your own.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="I accept the covenant", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _guard_home_guild(interaction, self.bot):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            rules = rules_service.get_rules_version_by_id(connection, self.rules_version_id)
            if not rules.is_active:
                await interaction.followup.send(
                    "This rules version is no longer active. Use `/rules` for the current one.",
                    ephemeral=True,
                )
                return
            result = rules_service.accept_rules_version(
                connection,
                guild_id=self.guild_id,
                user_id=interaction.user.id,
                rules_version_id=rules.id,
                accepted_via="button",
                actor_user_id=interaction.user.id,
            )

        message = await render_persona_text(
            feature_key="rules_acceptance",
            task=(
                "Write one short confirmation that the user accepted the server rules covenant. "
                "If they had already accepted, acknowledge that without scolding."
            ),
            context={
                "guild": interaction.guild.name if interaction.guild else "unknown guild",
                "version": rules.version_tag,
                "already_accepted": result.already_accepted,
            },
            fallback=(
                "Your acceptance was already recorded."
                if result.already_accepted
                else "Your acceptance has been recorded."
            ),
        )
        await interaction.followup.send(message, ephemeral=True)


@app_commands.guild_only()
class Rules(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rules", description="Read and accept the server covenant.")
    async def rules(self, interaction: discord.Interaction) -> None:
        if not await _guard_home_guild(interaction, self.bot):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                active_rules = rules_service.get_active_rules(connection, guild_id=_guild_id(interaction))
        except rules_service.RulesNotConfigured:
            await interaction.edit_original_response(content="No active rules covenant is configured yet.")
            return

        if active_rules is None:
            await interaction.edit_original_response(content="No active rules covenant is configured yet.")
            return

        embed = await build_rules_embed(interaction=interaction, rules=active_rules, mode="preview")
        view = CovenantGateView(
            bot=self.bot,
            guild_id=_guild_id(interaction),
            rules_version_id=active_rules.id,
            accept_label=active_rules.accept_label,
            author_id=interaction.user.id,
        )
        await interaction.edit_original_response(embed=embed, view=view)


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class RulesAdmin(commands.GroupCog, group_name="rules-admin"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _guard(self, interaction: discord.Interaction) -> bool:
        return await _guard_home_guild(interaction, self.bot)

    @app_commands.command(name="set", description="Create or update a rules covenant version.")
    @app_commands.describe(
        version_tag="Short version label, such as v1 or 2026-06.",
        title="Embed title for the covenant.",
        intro_text="Fallback intro line if AI is unavailable.",
        body_text="Full rules text.",
        accept_label="Button label for acceptance.",
        activate="Immediately make this version active.",
    )
    async def set_rules(
        self,
        interaction: discord.Interaction,
        version_tag: str,
        title: str,
        intro_text: str,
        body_text: str,
        accept_label: str = "I accept the covenant",
        activate: bool = False,
    ) -> None:
        if not await self._guard(interaction):
            return

        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                rules = rules_service.upsert_rules_version(
                    connection,
                    guild_id=_guild_id(interaction),
                    version_tag=version_tag,
                    title=title,
                    intro_text=intro_text,
                    body_text=body_text,
                    accept_label=accept_label,
                    actor_user_id=interaction.user.id,
                )
                if activate:
                    rules = rules_service.activate_rules_version(
                        connection,
                        guild_id=_guild_id(interaction),
                        version_tag=version_tag,
                        actor_user_id=interaction.user.id,
                    )
        except rules_service.RulesError as exc:
            await interaction.response.send_message(f"Rules error: {exc}", ephemeral=True)
            return

        status = "active" if rules.is_active else "stored"
        await interaction.response.send_message(
            f"Rules covenant `{rules.version_tag}` is now {status}.",
            ephemeral=True,
        )

    @app_commands.command(name="activate", description="Make one covenant version active.")
    async def activate(self, interaction: discord.Interaction, version_tag: str) -> None:
        if not await self._guard(interaction):
            return

        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                active_rules = rules_service.activate_rules_version(
                    connection,
                    guild_id=_guild_id(interaction),
                    version_tag=version_tag,
                    actor_user_id=interaction.user.id,
                )
        except rules_service.RulesError as exc:
            await interaction.response.send_message(f"Rules error: {exc}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Rules covenant `{active_rules.version_tag}` is now active.",
            ephemeral=True,
        )

    @app_commands.command(name="preview", description="Preview a covenant version without publishing it.")
    async def preview(self, interaction: discord.Interaction, version_tag: str | None = None) -> None:
        if not await self._guard(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                if version_tag:
                    rules = rules_service.get_rules_version(
                        connection,
                        guild_id=_guild_id(interaction),
                        version_tag=version_tag,
                    )
                else:
                    rules = rules_service.get_active_rules(connection, guild_id=_guild_id(interaction))
        except rules_service.RulesError as exc:
            await interaction.edit_original_response(content=f"Rules error: {exc}")
            return

        if rules is None:
            await interaction.edit_original_response(content="No rules covenant version is available.")
            return

        embed = await build_rules_embed(interaction=interaction, rules=rules, mode="admin-preview")
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="publish", description="Publish the active Covenant Gate to a channel.")
    async def publish(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not await self._guard(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                active_rules = rules_service.get_active_rules(connection, guild_id=_guild_id(interaction))
        except rules_service.RulesError as exc:
            await interaction.edit_original_response(content=f"Rules error: {exc}")
            return

        if active_rules is None:
            await interaction.edit_original_response(content="No active rules covenant is configured yet.")
            return

        embed = await build_rules_embed(interaction=interaction, rules=active_rules, mode="publish")
        view = CovenantGateView(
            bot=self.bot,
            guild_id=_guild_id(interaction),
            rules_version_id=active_rules.id,
            accept_label=active_rules.accept_label,
            persistent=True,
        )
        message = await channel.send(embed=embed, view=view)
        self.bot.add_view(view, message_id=message.id)

        with managed_connection(_database_path(self.bot)) as connection:
            rules_service.update_published_message(
                connection,
                rules_version_id=active_rules.id,
                channel_id=channel.id,
                message_id=message.id,
                actor_user_id=interaction.user.id,
            )

        await interaction.edit_original_response(
            content=f"Published Covenant Gate for `{active_rules.version_tag}` to {channel.mention}."
        )

    @app_commands.command(name="summary", description="Show active covenant acceptance count.")
    async def summary(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return

        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                summary = rules_service.summarize_acceptance(connection, guild_id=_guild_id(interaction))
        except rules_service.RulesError as exc:
            await interaction.response.send_message(f"Rules error: {exc}", ephemeral=True)
            return

        await interaction.response.send_message(
            "**Covenant acceptance**\n"
            "```txt\n"
            f"version        = {summary.version_tag}\n"
            f"rules_id       = {summary.rules_version_id}\n"
            f"accepted_count = {summary.accepted_count}\n"
            "```",
            ephemeral=True,
        )

    @app_commands.command(name="user", description="Show whether a user accepted the active covenant.")
    async def user(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await self._guard(interaction):
            return

        initialize_database(_database_path(self.bot))
        try:
            with managed_connection(_database_path(self.bot)) as connection:
                active_rules = rules_service.get_active_rules(connection, guild_id=_guild_id(interaction))
                acceptance = rules_service.get_acceptance_for_user(
                    connection,
                    guild_id=_guild_id(interaction),
                    user_id=user.id,
                    rules_version_id=active_rules.id if active_rules else None,
                )
        except rules_service.RulesError as exc:
            await interaction.response.send_message(f"Rules error: {exc}", ephemeral=True)
            return

        if active_rules is None:
            await interaction.response.send_message(
                "No active rules covenant is configured yet.",
                ephemeral=True,
            )
            return

        status = "accepted" if acceptance else "not accepted"
        accepted_at = acceptance.accepted_at if acceptance else "unset"
        accepted_via = acceptance.accepted_via if acceptance else "unset"
        await interaction.response.send_message(
            "**Covenant user status**\n"
            "```txt\n"
            f"user           = {user.id}\n"
            f"version        = {active_rules.version_tag}\n"
            f"status         = {status}\n"
            f"accepted_at    = {accepted_at}\n"
            f"accepted_via   = {accepted_via}\n"
            "```",
            ephemeral=True,
        )

    @app_commands.command(name="list", description="List recent covenant versions.")
    async def list_versions(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        if not await self._guard(interaction):
            return

        initialize_database(_database_path(self.bot))
        with managed_connection(_database_path(self.bot)) as connection:
            versions = rules_service.list_rules_versions(
                connection,
                guild_id=_guild_id(interaction),
                limit=limit,
            )

        if not versions:
            await interaction.response.send_message("No covenant versions exist yet.", ephemeral=True)
            return

        lines = ["**Covenant versions**", "```txt"]
        for rules in versions:
            marker = "active" if rules.is_active else "stored"
            lines.append(f"{rules.version_tag:<16} {marker:<8} id={rules.id}")
        lines.append("```")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


def _register_persistent_views(bot: commands.Bot) -> None:
    initialize_database(_database_path(bot))
    with managed_connection(_database_path(bot)) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM rules_versions
            WHERE is_active = 1
              AND published_message_id IS NOT NULL
              AND published_channel_id IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            view = CovenantGateView(
                bot=bot,
                guild_id=int(row["guild_id"]),
                rules_version_id=int(row["id"]),
                accept_label=str(row["accept_label"]),
                persistent=True,
            )
            bot.add_view(view, message_id=int(row["published_message_id"]))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Rules(bot))
    await bot.add_cog(RulesAdmin(bot))
    _register_persistent_views(bot)
