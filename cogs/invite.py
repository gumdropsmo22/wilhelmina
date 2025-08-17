from __future__ import annotations
import os
import discord
from discord import app_commands
from discord.ext import commands
from utils import embeds

SCOPES = ("bot", "applications.commands")

def _perm_value(app_env: str) -> int:
    if app_env.lower() == "development":
        return 8
    p = discord.Permissions(
        view_channel=True,
        send_messages=True,
        embed_links=True,
        read_message_history=True,
        add_reactions=True,
        use_application_commands=True,
    )
    return p.value

def _invite_url(client_id: str, perms: int) -> str:
    scopes = "%20".join(SCOPES)
    return f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions={perms}&scope={scopes}"

class Invite(commands.Cog):
    """Provides /invite to generate the OAuth2 URL."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="invite", description="Get the bot's OAuth2 invite link.")
    async def invite(self, interaction: discord.Interaction):
        client_id = os.getenv("CLIENT_ID", "").strip()
        app_env = os.getenv("APP_ENV", "development")
        if not client_id:
            await interaction.response.send_message(
                "CLIENT_ID is not set in the environment.", ephemeral=True
            )
            return
        url = _invite_url(client_id, _perm_value(app_env))
        e = embeds.system_embed(
            header="▒▒ INVITE ▒▒",
            description=f"[Authorize Wilhelmina]({url})\n`APP_ENV={app_env}` · `perms={_perm_value(app_env)}`",
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Invite(bot))
