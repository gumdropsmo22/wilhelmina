from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from config.settings import RuntimeSettings, SettingsError, load_settings

logger = logging.getLogger("wilhelmina")
REGISTRY_EXTENSION = "cogs.coven_registry"


def configure_logging(level_name: str) -> None:
    """Configure process logging once at startup."""

    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_intents(settings: RuntimeSettings) -> discord.Intents:
    """Build Discord gateway intents from enabled features."""

    intents = discord.Intents.default()
    if settings.is_cog_enabled("cogs.rules"):
        intents.members = True
    return intents


async def load_cogs(bot: commands.Bot, settings: RuntimeSettings) -> dict[str, list[str]]:
    """Load enabled Discord extensions and report loaded/skipped/failed cogs."""

    report: dict[str, list[str]] = {
        "loaded": [],
        "skipped": [],
        "failed": [],
    }

    for flag in settings.cog_flags:
        if not settings.is_cog_enabled(flag.extension):
            report["skipped"].append(flag.extension)
            logger.info(
                "cog_skipped extension=%s env_var=%s required=%s",
                flag.extension,
                flag.env_var,
                flag.required,
            )
            continue

        try:
            await bot.load_extension(flag.extension)
        except commands.ExtensionAlreadyLoaded:
            report["loaded"].append(flag.extension)
            logger.warning("cog_already_loaded extension=%s", flag.extension)
        except (
            commands.ExtensionNotFound,
            commands.NoEntryPointError,
            commands.ExtensionFailed,
        ):
            report["failed"].append(flag.extension)
            logger.exception(
                "cog_load_failed extension=%s env_var=%s required=%s",
                flag.extension,
                flag.env_var,
                flag.required,
            )
            if flag.required:
                raise
        except Exception:
            report["failed"].append(flag.extension)
            logger.exception(
                "cog_load_failed_unexpected extension=%s env_var=%s required=%s",
                flag.extension,
                flag.env_var,
                flag.required,
            )
            if flag.required:
                raise
        else:
            report["loaded"].append(flag.extension)
            logger.info(
                "cog_loaded extension=%s env_var=%s required=%s",
                flag.extension,
                flag.env_var,
                flag.required,
            )

    if settings.is_cog_enabled("cogs.rules"):
        try:
            await bot.load_extension(REGISTRY_EXTENSION)
        except commands.ExtensionAlreadyLoaded:
            report["loaded"].append(REGISTRY_EXTENSION)
        except Exception:
            report["failed"].append(REGISTRY_EXTENSION)
            logger.exception("cog_load_failed extension=%s", REGISTRY_EXTENSION)
            raise
        else:
            report["loaded"].append(REGISTRY_EXTENSION)
            logger.info("cog_loaded extension=%s", REGISTRY_EXTENSION)

    return report


async def sync_application_commands(bot: commands.Bot, settings: RuntimeSettings) -> None:
    """Synchronize Discord application commands according to COMMAND_SYNC_MODE."""

    mode = settings.command_sync_mode

    if mode == "off":
        logger.info("command_sync_skipped mode=off")
        return

    if mode == "auto":
        mode = "guild" if settings.home_guild_id else "global"

    if mode == "guild":
        if settings.home_guild_id is None:
            raise SettingsError("HOME_GUILD_ID is required for guild command sync")
        guild = discord.Object(id=settings.home_guild_id)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(
            "command_sync_complete scope=guild guild_id=%s command_count=%s",
            settings.home_guild_id,
            len(synced),
        )
        return

    synced = await bot.tree.sync()
    logger.warning("command_sync_complete scope=global command_count=%s", len(synced))


class WilhelminaBot(commands.Bot):
    """Discord client for Wilhelmina."""

    def __init__(self, *, settings: RuntimeSettings) -> None:
        super().__init__(
            command_prefix="!",
            intents=build_intents(settings),
        )
        self.settings = settings
        self.start_ts = time.time()
        self.cog_load_report: dict[str, list[str]] = {
            "loaded": [],
            "skipped": [],
            "failed": [],
        }

    async def setup_hook(self) -> None:
        self.cog_load_report = await load_cogs(self, self.settings)
        await sync_application_commands(self, self.settings)

    async def on_ready(self) -> None:
        logger.info(
            "bot_online user=%s app_env=%s server_mode=%s sync_mode=%s home_guild_id=%s "
            "loaded_cogs=%s skipped_cogs=%s failed_cogs=%s",
            self.user,
            self.settings.app_env,
            self.settings.server_mode,
            self.settings.command_sync_mode,
            self.settings.home_guild_id,
            ",".join(self.cog_load_report["loaded"]) or "none",
            ",".join(self.cog_load_report["skipped"]) or "none",
            ",".join(self.cog_load_report["failed"]) or "none",
        )


def main() -> None:
    try:
        settings = load_settings()
    except SettingsError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    configure_logging(settings.log_level)

    bot = WilhelminaBot(settings=settings)
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
