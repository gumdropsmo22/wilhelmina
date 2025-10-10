import os, asyncio, discord
from discord.ext import commands

INTENTS = discord.Intents.default()
INTENTS.message_content = False
INTENTS.members = True
INTENTS.voice_states = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (latency {bot.latency*1000:.0f}ms)")
    await bot.tree.sync()

async def _load():
    await bot.load_extension("wilhelmina.cogs.oracles")

def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_BOT_TOKEN in environment.")
    asyncio.run(_load())
    bot.run(token)

if __name__ == "__main__":
    main()
