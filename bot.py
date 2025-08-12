import os, asyncio
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Wilhelmina online as {bot.user} (guilds: {len(bot.guilds)})")

async def load_cogs():
    try:
        await bot.load_extension("cogs.oracles")
    except Exception as e:
        print(f"Note: could not load cogs.oracles ({e})")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in environment.")
    asyncio.run(main())
