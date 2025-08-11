from __future__ import annotations
import discord
from typing import Optional

VIOLET = 0x6E00FF

def build_embed(
    title: Optional[str] = None,
    description: Optional[str] = None,
    *,
    trace: Optional[str] = None,
) -> discord.Embed:
    """Centralized embed style per spec."""
    emb = discord.Embed(
        title=title or "▒▒ MESSAGE ▒▒",
        description=description or "",
        color=VIOLET,
    )
    emb.set_author(name="WILHELMINA • SYSTEM")
    emb.set_footer(text="haunt://coven/wilhelmina")
    if trace:
        emb.add_field(name="trace", value=trace, inline=False)
    return emb
