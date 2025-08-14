import os, time, platform
import discord
from discord import app_commands
from discord.ext import commands

class Core(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="about", description="About this bot")
    async def about(self, interaction: discord.Interaction):
        msg = (
            f"**Wilhelmina** skeleton is alive. "
            f"Python {platform.python_version()} • discord.py {discord.__version__} "
            f"• env={os.getenv('APP_ENV','development')}"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="uptime", description="Show bot uptime")
    async def uptime(self, interaction: discord.Interaction):
        started = getattr(self.bot, "start_ts", time.time())
        secs = int(time.time() - started)
        h, r = divmod(secs, 3600); m, s = divmod(r, 60)
        await interaction.response.send_message(f"Uptime: {h}h {m}m {s}s", ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="sync", description="Admin: resync slash commands")
    async def sync(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Admins only.", ephemeral=True)
        dev = os.getenv("APP_ENV","development") == "development"
        gid = os.getenv("DEV_GUILD_ID")
        if dev and gid:
            guild = discord.Object(id=int(gid))
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            return await interaction.response.send_message(f"Synced {len(synced)} cmds to dev guild.", ephemeral=True)
        synced = await self.bot.tree.sync()
        await interaction.response.send_message(f"Synced {len(synced)} cmds globally.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))

async def load_cogs():
    await bot.load_extension('cogs.core')

