from __future__ import annotations
from discord.ext import commands
import discord
from utils.persona import say
from utils.embeds import build_embed

class Chat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return
        # Only plain text allowed in #chat-with-wilhelmina; elsewhere we reply with embeds.
        if msg.channel and getattr(msg.channel, "name", "") == "chat-with-wilhelmina":
            return  # handled by future conversational logic
        # Minimal playful nudge so we exercise the embed path without implementing chat yet.
        if self.bot.user and self.bot.user in msg.mentions:
            emb = build_embed(title="▒▒ PING ▒▒", description=say("You rang?"))
            await msg.reply(embed=emb, mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Chat(bot))
