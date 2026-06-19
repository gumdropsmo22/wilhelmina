from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services import help as help_service
from services.persona import render_persona_text

HELP_CATEGORY_CHOICES = [
    app_commands.Choice(name="Core", value="core"),
    app_commands.Choice(name="Divination", value="divination"),
    app_commands.Choice(name="Server", value="server"),
    app_commands.Choice(name="Miscellany", value="misc"),
]


class HelpCategorySelect(discord.ui.Select):
    """Category selector for the Living Command Grimoire."""

    def __init__(self, view: "HelpView") -> None:
        self.grimoire_view = view
        options = [
            discord.SelectOption(
                label=help_service.CATEGORY_LABELS.get(category, category.title()),
                value=category,
                default=category == view.category,
            )
            for category in view.categories
        ]
        if not options:
            options = [discord.SelectOption(label="Miscellany", value="misc", default=True)]
        super().__init__(placeholder="Choose a grimoire wing…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.grimoire_view.category = self.values[0]
        self.grimoire_view.page = 0
        await self.grimoire_view.render(interaction)


class HelpView(discord.ui.View):
    """Interactive grimoire view with category and page controls."""

    def __init__(
        self,
        *,
        author_id: int,
        entries: tuple[help_service.HelpEntry, ...],
        category: str,
        page: int = 0,
    ) -> None:
        super().__init__(timeout=600)
        self.author_id = int(author_id)
        self.entries = entries
        self.categories = help_service.available_categories(entries)
        self.category = category
        self.page = page
        self.add_item(HelpCategorySelect(self))
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "This grimoire opened for another hand. Summon your own with `/help`.",
            ephemeral=True,
        )
        return False

    def current_page(self) -> help_service.HelpPage:
        return help_service.build_page(self.entries, category=self.category, page=self.page)

    def _sync_buttons(self) -> None:
        page = self.current_page()
        self.previous_page.disabled = page.page <= 0
        self.next_page.disabled = page.page >= page.total_pages - 1

        for item in self.children:
            if isinstance(item, HelpCategorySelect):
                for option in item.options:
                    option.default = option.value == page.category

    async def intro_text(self, interaction: discord.Interaction, page: help_service.HelpPage) -> str:
        return await render_persona_text(
            feature_key="help",
            task=(
                "Write one concise opening line for a dynamic command help embed. "
                "Do not list commands. Do not mention admin commands."
            ),
            context={
                "guild": interaction.guild.name if interaction.guild else "direct message",
                "category": page.category_label,
                "visible_commands": ", ".join(entry.display_name for entry in page.entries) or "none",
                "coming_soon": ", ".join(page.coming_soon) or "none",
            },
        )

    async def render(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        page = self.current_page()
        self._sync_buttons()
        intro = await self.intro_text(interaction, page)
        embed = help_service.build_embed(page, intro=intro)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.page = max(0, self.page - 1)
        await self.render(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.page += 1
        await self.render(interaction)


class Help(commands.Cog):
    """Living Command Grimoire."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Open Wilhelmina's living command grimoire.")
    @app_commands.describe(
        category="Optional grimoire category to open first.",
        public="Show the grimoire publicly instead of only to you.",
    )
    @app_commands.choices(category=HELP_CATEGORY_CHOICES)
    async def help(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str] | None = None,
        public: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=not public, thinking=True)
        entries = help_service.collect_public_commands(self.bot)
        categories = help_service.available_categories(entries)
        requested_category = category.value if category is not None else None
        selected = requested_category if requested_category in categories else (
            categories[0] if categories else "misc"
        )
        page = help_service.build_page(entries, category=selected)
        intro = await render_persona_text(
            feature_key="help",
            task=(
                "Write one concise opening line for Wilhelmina's dynamic command grimoire. "
                "Do not list commands. Do not mention admin commands."
            ),
            context={
                "guild": interaction.guild.name if interaction.guild else "direct message",
                "category": page.category_label,
                "visible_commands": ", ".join(entry.display_name for entry in page.entries) or "none",
                "available_categories": ", ".join(categories) or "none",
            },
        )
        view = HelpView(
            author_id=interaction.user.id,
            entries=entries,
            category=page.category,
            page=page.page,
        )
        embed = help_service.build_embed(page, intro=intro)
        await interaction.edit_original_response(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
