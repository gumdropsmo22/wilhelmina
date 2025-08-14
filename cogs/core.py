import os, time, discord
from discord import app_commands
from discord.ext import commands

APP_ENV = os.getenv("APP_ENV","development")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")

class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start = time.time()

    @app_commands.command(name="about", description="About this bot")
    async def about(self, interaction: discord.Interaction):
        await interaction.response.send_message("Wilhelmina core ready.", ephemeral=True)

    @app_commands.command(name="uptime", description="Show bot uptime")
    async def uptime(self, interaction: discord.Interaction):
        s = int(time.time() - self.start)
        h, r = divmod(s, 3600); m, s = divmod(r, 60)
        await interaction.response.send_message(f"Uptime: {h}h {m}m {s}s", ephemeral=True)

    @app_commands.command(name="sync", description="Resync slash commands")
    @app_commands.default_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        if APP_ENV == "development" and DEV_GUILD_ID:
            guild = discord.Object(id=int(DEV_GUILD_ID))
            self.bot.tree.copy_global_to(guild=guild)
            cmds = await self.bot.tree.sync(guild=guild)
            await interaction.response.send_message(f"Synced {len(cmds)} to dev guild.", ephemeral=True)
        else:
            cmds = await self.bot.tree.sync()
            await interaction.response.send_message(f"Synced {len(cmds)} globally.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
