from __future__ import annotations

import discord

from services.coven_registry import RegistryEntry

REGISTRY_COLOR = 0x4B164C


def public_card(entry: RegistryEntry) -> discord.Embed:
    embed = discord.Embed(
        title="☾ 𝔗𝔥𝔢 ℭ𝔬𝔳𝔢𝔫 ℜ𝔢𝔤𝔦𝔰𝔱𝔯𝔶 ☽",
        description="━━━━━━━━ ✦ ━━━━━━━━",
        color=REGISTRY_COLOR,
    )
    embed.add_field(name="COVEN MARK", value=entry.display_mark, inline=False)
    embed.add_field(name="SUBJECT", value=entry.display_name, inline=True)
    embed.add_field(name="CLASSIFICATION", value=entry.classification, inline=True)
    embed.add_field(name="STATUS", value=entry.status.title(), inline=True)
    if entry.inducted_at:
        embed.add_field(name="INDUCTED", value=entry.inducted_at, inline=False)
    embed.set_footer(text="The ledger remembers.")
    return embed


def admin_profile(entry: RegistryEntry) -> discord.Embed:
    embed = public_card(entry)
    embed.title = "☾ 𝔓𝔯𝔦𝔳𝔞𝔱𝔢 ℭ𝔬𝔳𝔢𝔫 𝔉𝔦𝔩𝔢 ☽"
    values = (
        ("DISCORD USER ID", str(entry.user_id)),
        ("REGISTRY NUMBER", str(entry.registry_number)),
        ("SYSTEM ENTRY", str(entry.is_system).lower()),
        ("JOINED", entry.joined_at or "unset"),
        ("DEPARTED", entry.departed_at or "unset"),
        ("COVENANT VERSION ID", str(entry.covenant_version_id or "unset")),
        ("NOTICE MESSAGE ID", str(entry.induction_notice_message_id or "unset")),
        ("CREATED", entry.created_at),
        ("UPDATED", entry.updated_at),
    )
    for name, value in values:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="Administrator view • future memory records remain sealed here.")
    return embed


def index_card(entries: list[RegistryEntry], *, page: int, pages: int, total: int) -> discord.Embed:
    embed = discord.Embed(
        title="☾ 𝔗𝔥𝔢 ℭ𝔬𝔳𝔢𝔫 ℜ𝔢𝔤𝔦𝔰𝔱𝔯𝔶 ☽",
        description="━━━━━━━━ ✦ ━━━━━━━━\nThe public index. The private files remain private.",
        color=REGISTRY_COLOR,
    )
    if not entries:
        embed.add_field(name="THE LEDGER", value="No entries have been recorded yet.", inline=False)
    for entry in entries:
        embed.add_field(
            name=f"{entry.display_mark} • {entry.display_name}",
            value=f"{entry.classification} • {entry.status.title()}",
            inline=False,
        )
    embed.set_footer(text=f"Page {page}/{pages} • {total} recorded")
    return embed


def induction_card(member: discord.Member, entry: RegistryEntry) -> discord.Embed:
    embed = discord.Embed(
        title="☾ 𝔠𝔬𝔳𝔢𝔫 𝔦𝔫𝔡𝔲𝔠𝔱𝔦𝔬𝔫 ☽",
        description="━━━━━━━━ ✦ ━━━━━━━━",
        color=REGISTRY_COLOR,
    )
    embed.add_field(name="SUBJECT", value=member.mention, inline=False)
    embed.add_field(name="COVEN MARK", value=entry.display_mark, inline=False)
    embed.add_field(name="CLASSIFICATION", value=entry.classification, inline=True)
    embed.add_field(name="STATUS", value=entry.status.title(), inline=True)
    embed.set_footer(text="The ledger has opened.")
    return embed
