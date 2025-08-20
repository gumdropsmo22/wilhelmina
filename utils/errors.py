"""Utilities for error handling setup."""

from __future__ import annotations

import logging
from discord.ext import commands

__all__ = ["register_error_handler"]

log = logging.getLogger(__name__)

_registered: bool = False


def register_error_handler(bot: commands.Bot) -> None:
    """Register the centralized error handler cog.

    This schedules loading of the :mod:`cogs.errors` extension before the bot
    connects. The function is idempotent and safe to call multiple times.

    Parameters
    ----------
    bot:
        The bot instance to attach the error handler to.
    """

    global _registered
    if _registered:
        log.debug("Error handler already registered")
        return
    _registered = True

    async def load_errors() -> None:
        try:
            await bot.load_extension("cogs.errors")
            log.info("Errors cog loaded")
        except Exception:
            log.exception("Failed to load errors cog")

    bot.add_setup_hook(load_errors)

