#!/usr/bin/env python3
from __future__ import annotations
import os
import asyncio
import logging
import traceback

import discord
from discord.ext import commands

from utils.embeds import build_embed
from utils.persona import say
from config.settings import Settings

# Global flags enforced later by C11; we wire minimal guard now.
EMBEDS_ONLY = True

def _intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    voice = getattr(intents, "voice_states", None)
    if voice is not None:
        intents.voice_states = True
    return intents

class WilhelminaBot(commands.Bot):
    def __init__(self, settings: Settings):
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=_intents())
        self.settings = settings
        self.remove_command("help")  # we will provide our own later

    async def setup_hook(self):
        # Load cogs (minimal shells for now; real logic comes in future tasks).
        for cog in ("cogs.oracles", "cogs.chat"):
            try:
                await self.load_extension(cog)
            except Exception:
                logging.exception("Failed to load %s", cog)

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        logging.error("Command error: %s", error, exc_info=error)
        try:
            if EMBEDS_ONLY and ctx.channel and ctx.channel.name != "chat-with-wilhelmina":
                emb = build_embed(title="▒▒ ERROR ▒▒", description=say("Whoops. The ritual fizzled."))
                await ctx.reply(embed=emb, mention_author=False)
            else:
                await ctx.reply(say("Whoops. The ritual fizzled."), mention_author=False)
        except Exception:
            traceback.print_exc()

def main() -> None:
    settings = Settings.from_env()
    bot = WilhelminaBot(settings=settings)
    token = settings.discord_token
    if not token:
        raise RuntimeError("DISCORD_TOKEN is missing")
    bot.run(token)

if __name__ == "__main__":
    main()
