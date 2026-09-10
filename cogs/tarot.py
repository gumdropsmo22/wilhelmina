from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from services import tarot, tarot_artwork
from utils import embeds

VISIBILITY_CHOICES = [
    app_commands.Choice(name="Public", value="public"),
    app_commands.Choice(name="Private", value="private"),
]
EMBED_FIELD_VALUE_LIMIT = 1024


class Tarot(commands.GroupCog, group_name="tarot", group_description="Draw Tarot with Wilhelmina."):
    """Single-card and three-card Tarot readings."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="single", description="Draw one Tarot card and receive Wilhelmina's reading.")
    @app_commands.describe(
        visibility="Choose whether everyone in the channel or only you can see the reading.",
        question="Optional question for the card. Leave blank for a general reading.",
    )
    @app_commands.choices(visibility=VISIBILITY_CHOICES)
    async def single(
        self,
        interaction: discord.Interaction,
        visibility: app_commands.Choice[str],
        question: str | None = None,
    ) -> None:
        await self._run(
            interaction,
            spread=tarot.SpreadKind.SINGLE,
            visibility=visibility.value,
            question=question,
        )

    @app_commands.command(
        name="three",
        description="Draw Past / Present / Future and receive Wilhelmina's reading.",
    )
    @app_commands.describe(
        visibility="Choose whether everyone in the channel or only you can see the reading.",
        question="Optional question for the spread. Leave blank for a general reading.",
    )
    @app_commands.choices(visibility=VISIBILITY_CHOICES)
    async def three(
        self,
        interaction: discord.Interaction,
        visibility: app_commands.Choice[str],
        question: str | None = None,
    ) -> None:
        await self._run(
            interaction,
            spread=tarot.SpreadKind.THREE,
            visibility=visibility.value,
            question=question,
        )

    async def _run(
        self,
        interaction: discord.Interaction,
        *,
        spread: tarot.SpreadKind,
        visibility: str,
        question: str | None,
    ) -> None:
        private = visibility == "private"
        try:
            reading = tarot.draw_reading(spread, question=question)
        except tarot.TarotQuestionRejected as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=private)
        interpretation = await tarot.generate_interpretation(reading)
        reading_embed = _reading_embed(reading, interpretation)
        art_embeds, art_files = _artwork_payload(reading)

        await interaction.followup.send(
            embeds=[reading_embed, *art_embeds],
            files=art_files,
            ephemeral=private,
        )


def _clip_field_value(value: str, *, limit: int = EMBED_FIELD_VALUE_LIMIT) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _reading_embed(
    reading: tarot.TarotReading,
    interpretation: tarot.TarotInterpretation,
) -> discord.Embed:
    header = (
        "▒▒ TAROT • SINGLE CARD ▒▒"
        if reading.spread is tarot.SpreadKind.SINGLE
        else "▒▒ TAROT • PAST / PRESENT / FUTURE ▒▒"
    )
    embed = embeds.system_embed(header=header, description=interpretation.text)

    if reading.question:
        embed.add_field(name="Question", value=_clip_field_value(reading.question), inline=False)

    for drawn in reading.cards:
        keywords = " · ".join(drawn.keywords)
        embed.add_field(
            name=f"{drawn.position} — {drawn.card.name}",
            value=f"**{drawn.orientation.label}**\n{keywords}",
            inline=False,
        )
    return embed


def _artwork_payload(
    reading: tarot.TarotReading,
) -> tuple[list[discord.Embed], list[discord.File]]:
    art_embeds: list[discord.Embed] = []
    art_files: list[discord.File] = []

    for drawn in reading.cards:
        prepared = tarot_artwork.prepare_artwork(drawn)
        if prepared is None:
            continue

        art_file = discord.File(io.BytesIO(prepared.data), filename=prepared.filename)
        art_embed = discord.Embed(
            title=f"{drawn.position} — {drawn.card.name} — {drawn.orientation.label}",
            color=0x6E00FF,
        )
        if drawn.orientation is tarot.Orientation.REVERSED and not prepared.visually_reversed:
            art_embed.description = "Reversed draw • artwork displayed in its source orientation."
        art_embed.set_image(url=f"attachment://{prepared.filename}")
        art_embeds.append(art_embed)
        art_files.append(art_file)

    return art_embeds, art_files


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tarot(bot))
