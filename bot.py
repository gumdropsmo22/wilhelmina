import asyncio, logging, sys
import discord
from discord.ext import commands
from discord import app_commands
from config import settings

# logging
level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(stream=sys.stdout, level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("wilhelmina")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
_synced = False

@bot.event
async def on_ready():
    global _synced
    log.info("Online as %s (guilds: %d)", bot.user, len(bot.guilds))
    if not _synced:
        try:
            if settings.APP_ENV == "development" and settings.DEV_GUILD_ID:
                guild = discord.Object(id=int(settings.DEV_GUILD_ID))
                synced = await bot.tree.sync(guild=guild)
                log.info("[DEV] Synced %d commands to guild %s", len(synced), settings.DEV_GUILD_ID)
            else:
                synced = await bot.tree.sync()
                log.info("[GLOBAL] Synced %d commands", len(synced))
        except Exception as e:
            log.exception("Sync failed: %s", e)
        _synced = True

@bot.tree.command(name="ping", description="Health check for Wilhelmina")
async def ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {ms} ms • env={settings.APP_ENV}", ephemeral=True)

async def load_cogs():
    try:
        await bot.load_extension("cogs.oracles")
    except Exception as e:
        log.warning("Could not load cogs.oracles: %s", e)

async def main():
    token = settings.require_token()
    async with bot:
        await load_cogs()
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
