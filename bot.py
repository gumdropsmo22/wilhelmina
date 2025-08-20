import asyncio, os
from pathlib import Path
import discord
from discord.ext import commands

from utils.interactions import register_default_ephemeral
from utils.errors import register_error_handler

# load .env (no extra deps)
envp = Path(".env")
if envp.exists():
    for line in envp.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

TOKEN = os.getenv("DISCORD_TOKEN")
APP_ENV = os.getenv("APP_ENV", "development")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
register_default_ephemeral(True)
register_error_handler(bot)

async def load_cogs():
    await bot.load_extension("cogs.core")
    await bot.load_extension("cogs.help")

@bot.event
async def on_ready():
    print(f"Online as {bot.user}")
    if APP_ENV == "development" and DEV_GUILD_ID:
        guild = discord.Object(id=int(DEV_GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"[DEV] Synced {len(synced)} commands to guild {DEV_GUILD_ID}")
    else:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global commands")

def main():
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    async def runner():
        async with bot:
            await load_cogs()
            await bot.start(TOKEN)
    asyncio.run(runner())

if __name__ == "__main__":
    main()
