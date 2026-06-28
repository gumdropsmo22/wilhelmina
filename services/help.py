from __future__ import annotations

from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands

ADMIN_ROOTS = {"admin", "rules-admin"}
CATEGORY_LABELS = {
    "core": "Basics",
    "divination": "Divination",
    "server": "Server",
    "misc": "Loose Ends",
}
CATEGORY_DESCRIPTIONS = {
    "core": "Core commands for checking what Wilhelmina is, whether she is alive, and how to use the obvious without making it a production.",
    "divination": "Dice, fortunes, and other questionable methods of outsourcing your judgment.",
    "server": "Rules, access, and the machinery keeping this place from collapsing into decorative rubble.",
    "misc": "Commands that exist outside the cleaner categories, because apparently not everything has the dignity to fit.",
}
CATEGORY_ORDER = ("core", "divination", "server", "misc")
DEFAULT_CATEGORY_MAP = {
    "about": "core",
    "uptime": "core",
    "invite": "core",
    "help": "server",
    "rules": "server",
    "roll": "divination",
    "8ball": "divination",
    "fortune": "divination",
}
COMING_SOON = {
    "divination": ("/tarot", "/readings", "/rituals"),
    "server": ("/welcome", "/broadcast"),
}


@dataclass(frozen=True)
class HelpEntry:
    """One public slash command entry in the Command Grimoire."""

    path: str
    description: str
    category: str

    @property
    def display_name(self) -> str:
        return f"/{self.path}"


@dataclass(frozen=True)
class HelpPage:
    """A rendered slice of the command grimoire."""

    category: str
    category_label: str
    entries: tuple[HelpEntry, ...]
    coming_soon: tuple[str, ...]
    page: int
    total_pages: int


def command_path(command: app_commands.Command) -> str:
    """Return a slash-style command path without the leading slash."""

    parts = [command.name]
    parent = command.parent
    while parent is not None:
        parts.append(parent.name)
        parent = parent.parent
    return " ".join(reversed(parts))


def command_root(command: app_commands.Command) -> str:
    """Return the first path component for a slash command."""

    return command_path(command).split(" ", 1)[0]


def is_public_command(command: app_commands.Command) -> bool:
    """Return whether a command belongs in the public help grimoire."""

    root = command_root(command)
    if root in ADMIN_ROOTS:
        return False

    extras = getattr(command, "extras", None) or {}
    if extras.get("hidden_from_help"):
        return False

    return True


def collect_public_commands(bot: commands.Bot) -> tuple[HelpEntry, ...]:
    """Collect public slash commands from the live command tree."""

    entries: list[HelpEntry] = []
    for command in bot.tree.walk_commands():
        if isinstance(command, app_commands.Group):
            continue
        if not isinstance(command, app_commands.Command):
            continue
        if not is_public_command(command):
            continue

        root = command_root(command)
        category = DEFAULT_CATEGORY_MAP.get(root, "misc")
        entries.append(
            HelpEntry(
                path=command_path(command),
                description=command.description or "No description has been written yet.",
                category=category,
            )
        )

    return tuple(sorted(entries, key=lambda entry: (category_index(entry.category), entry.path)))


def category_index(category: str) -> int:
    """Sort known categories before unknown ones."""

    try:
        return CATEGORY_ORDER.index(category)
    except ValueError:
        return len(CATEGORY_ORDER)


def available_categories(entries: tuple[HelpEntry, ...]) -> tuple[str, ...]:
    """Return categories that currently have visible commands."""

    categories = {entry.category for entry in entries}
    ordered = [category for category in CATEGORY_ORDER if category in categories]
    ordered.extend(sorted(categories.difference(CATEGORY_ORDER)))
    return tuple(ordered)


def build_page(
    entries: tuple[HelpEntry, ...],
    *,
    category: str | None = None,
    page: int = 0,
    per_page: int = 6,
) -> HelpPage:
    """Build one category page for the Command Grimoire."""

    categories = available_categories(entries)
    selected = category if category in categories else (categories[0] if categories else "misc")
    filtered = tuple(entry for entry in entries if entry.category == selected)
    total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
    safe_page = max(0, min(page, total_pages - 1))
    start = safe_page * per_page
    return HelpPage(
        category=selected,
        category_label=CATEGORY_LABELS.get(selected, selected.replace("_", " ").title()),
        entries=filtered[start : start + per_page],
        coming_soon=COMING_SOON.get(selected, ()),
        page=safe_page,
        total_pages=total_pages,
    )


def build_embed(page: HelpPage, *, intro: str) -> discord.Embed:
    """Render a grimoire page as a Discord embed."""

    embed = discord.Embed(
        title=f"Wilhelmina's Command Grimoire — {page.category_label}",
        description=intro,
        color=0x6E00FF,
    )
    embed.set_author(name="WILHELMINA • GRIMOIRE", icon_url="cdn/witch-sigil.png")

    category_description = CATEGORY_DESCRIPTIONS.get(page.category)
    if category_description:
        embed.add_field(name="This section", value=category_description, inline=False)

    if not page.entries:
        embed.add_field(
            name="Nothing here yet",
            value="No commands are listed here yet. Tragic, but survivable.",
            inline=False,
        )
    else:
        for entry in page.entries:
            embed.add_field(name=entry.display_name, value=entry.description, inline=False)

    if page.coming_soon:
        embed.add_field(
            name="Locked for Later",
            value=", ".join(page.coming_soon),
            inline=False,
        )

    embed.set_footer(text=f"Page {page.page + 1}/{page.total_pages} • haunt://coven/grimoire")
    return embed
