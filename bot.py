from __future__ import annotations

import logging

import discord
from discord.ext import commands

from config.settings import RuntimeSettings, SettingsError, load_settings


logger = logging.getLogger("wilhelmina")


def configure_logging(level_name: str) -> None:
    """Configure process logging once at startup."""

    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_intents(settings: RuntimeSettings) -> discord.Intents:
    """Build Discord gateway intents from enabled features.

    Current active cogs only need the default intents. Future feature modules
    should expand this function instead of enabling privileged intents globally.
    """

    intents = discord.Intents.default()
    return intents


async def load_cogs(bot: commands.Bot, settings: RuntimeSettings) -> dict[str, list[str]]:
    """Load enabled Discord extensions and report loaded/skipped/failed cogs.

    Required cogs fail startup if they cannot load. Optional cogs are logged and
    skipped so unfinished features do not kill the whole runtime.
    """

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

    return report


async def sync_application_commands(bot: commands.Bot, settings: RuntimeSettings) -> None:
    """Synchronize Discord application commands according to COMMAND_SYNC_MODE."""

    mode = settings.command_sync_mode

    if mode == "off":
        logger.info("command_sync_skipped mode=off")
        return

    if mode == "auto":
        mode = "dev" if settings.app_env == "development" and settings.dev_guild_id else "global"

    if mode == "dev":
        if settings.dev_guild_id is None:
            raise SettingsError("DEV_GUILD_ID is required for dev command sync")

        guild = discord.Object(id=settings.dev_guild_id)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(
            "command_sync_complete scope=dev guild_id=%s command_count=%s",
            settings.dev_guild_id,
            len(synced),
        )
        return

    synced = await bot.tree.sync()
    logger.info("command_sync_complete scope=global command_count=%s", len(synced))


class WilhelminaBot(commands.Bot):
    """Discord client for Wilhelmina."""

    def __init__(self, *, settings: RuntimeSettings) -> None:
        super().__init__(
            command_prefix="!",
            intents=build_intents(settings),
        )
        self.settings = settings
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
            "bot_online user=%s app_env=%s sync_mode=%s loaded_cogs=%s skipped_cogs=%s failed_cogs=%s",
            self.user,
            self.settings.app_env,
            self.settings.command_sync_mode,
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
