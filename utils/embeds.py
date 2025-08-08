import discord
from datetime import datetime, timezone


def system_embed(header: str = None, description: str = "", include_trace: bool = False) -> discord.Embed:
    """
    Create a Discord Embed with Wilhelmina's system style (haunted-glitch aesthetic).
    :param header: Optional ASCII header to display (e.g., '▒▒ ROLL ▒▒').
    :param description: Main content of the embed.
    :param include_trace: If True, include a generated "trace" field with glitchy debug info.
    :return: discord.Embed object styled accordingly.
    """
    # Base embed with toxic violet color
    embed = discord.Embed(color=0x6E00FF, description=description)
    # Set author name and icon for system identity
    embed.set_author(name="WILHELMINA • SYSTEM", icon_url="cdn/witch-sigil.png")
    # If a header text is provided, use it as the embed title (glitchy ASCII header inside embed)
    if header:
        embed.title = header
    # Optionally add a "trace" field with pseudo-technical glitch info at the bottom
    if include_trace:
        # Generate trace content: random signature, packet loss %, and a random omen phrase
        import random
        sig = random.randint(0, 0xFFFF)  # 16-bit hex signature
        loss = random.randint(0, 9)      # loss percentage 0-9%
        omens = [
            "mirror hums", "candle flickers", "void stares back",
            "cat hisses", "window whispers", "flames dance",
            "bones rattle", "ravens caw", "skull smiles", "mist rises"
        ]
        omen = random.choice(omens)
        trace_value = f"sig=0x{sig:04X} · loss={loss}% · omen=\"{omen}\""
        # Add as a field with no title (zero-width space as name to hide label)
        embed.add_field(name="\u200b", value=trace_value, inline=False)
    # Timestamp (UTC) for system log style
    embed.timestamp = datetime.now(timezone.utc)
    # Footer with custom protocol URL and glitch icon
    embed.set_footer(text="haunt://coven/wilhelmina", icon_url="cdn/glitch-dot.gif")
    return embed
