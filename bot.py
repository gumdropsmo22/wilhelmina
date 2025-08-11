#!/usr/bin/env python3
from __future__ import annotations
import logging

import discord
from discord.ext import commands

from config.settings import Settings
from utils.embeds import system_embed as build_embed
from utils import logging as wlog


def say(text: str) -> str:
    return text


class WilhelminaBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings

    async def setup_hook(self) -> None:
        try:
            await self.load_extension("cogs.oracles")
        except Exception as exc:  # pragma: no cover - best effort
            logging.exception("Failed to load cog: %s", exc)

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        logging.error("Command error: %s", error, exc_info=error)
        wlog.log_exception(
            "command_error",
            user_id=getattr(ctx.author, "id", None),
            channel_id=getattr(ctx.channel, "id", None),
        )
        try:
            if self.settings.embeds_only and ctx.channel and ctx.channel.name != "chat-with-wilhelmina":
                emb = build_embed(header="▒▒ ERROR ▒▒", description=say("Whoops. The ritual fizzled."))
                await ctx.send(embed=emb)
            else:
                await ctx.send("Whoops. The ritual fizzled.")
        except Exception:  # pragma: no cover - safety net
            logging.exception("Failed to send command error message")


def main() -> None:
    wlog.configure()
    settings = Settings.from_env()
    bot = WilhelminaBot(settings=settings)
    token = settings.discord_token
    if not token:
        raise RuntimeError("DISCORD_TOKEN not provided")
    bot.run(token)


if __name__ == "__main__":
    main()
