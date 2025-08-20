"""Utility functions for Discord interaction handling.

This module provides a helper to globally enforce default ephemeral
responses for Discord interactions. When registered, interaction responses
and follow-up webhook sends will automatically include ``ephemeral`` with a
configurable default unless the caller explicitly specifies otherwise.

Usage::
    from utils.interactions import register_default_ephemeral
    register_default_ephemeral(True)  # in bot.py after bot = commands.Bot(...)
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

import discord

try:
    from discord.webhook.async_ import InteractionWebhook as _IWebhook
except Exception:  # pragma: no cover - fallback for older discord versions
    _IWebhook = None  # type: ignore[assignment]

__all__ = ["register_default_ephemeral"]

logger = logging.getLogger(__name__)

# Module-level state to control default behaviour and ensure idempotency
_default_ephemeral: bool = True
_patched: bool = False
_original_send_message: Callable[..., Awaitable[Any]] | None = None
_original_webhook_send: Callable[..., Awaitable[Any]] | None = None


def register_default_ephemeral(ephemeral_default: bool = True) -> None:
    """Register global monkey patches enforcing default ephemeral replies.

    Parameters
    ----------
    ephemeral_default:
        If ``True`` (the default), all interaction responses and follow-up
        messages will be ephemeral unless ``ephemeral`` is explicitly provided
        by the caller. Setting this to ``False`` will default to non-ephemeral
        responses while still respecting explicit ``ephemeral`` values.

    Notes
    -----
    The function is idempotent: repeated calls will simply update the default
    without applying the patches multiple times.
    """

    global _default_ephemeral, _patched, _original_send_message, _original_webhook_send

    _default_ephemeral = ephemeral_default

    if _patched:
        logger.debug(
            "Default ephemeral already registered; updated default to %s", ephemeral_default
        )
        return

    # Store original methods for future reference/debugging
    _original_send_message = discord.InteractionResponse.send_message

    async def send_message_with_default(
        self: discord.InteractionResponse, *args: Any, **kwargs: Any
    ) -> Any:
        if "ephemeral" not in kwargs:
            kwargs["ephemeral"] = _default_ephemeral
            logger.debug(
                "Injected default ephemeral=%s into InteractionResponse.send_message", _default_ephemeral
            )
        return await _original_send_message(self, *args, **kwargs)  # type: ignore[misc]

    discord.InteractionResponse.send_message = send_message_with_default  # type: ignore[assignment]

    if _IWebhook is not None:
        _original_webhook_send = _IWebhook.send

        async def webhook_send_with_default(
            self: _IWebhook, *args: Any, **kwargs: Any
        ) -> Any:
            if "ephemeral" not in kwargs:
                kwargs["ephemeral"] = _default_ephemeral
                logger.debug(
                    "Injected default ephemeral=%s into InteractionWebhook.send", _default_ephemeral
                )
            return await _original_webhook_send(self, *args, **kwargs)  # type: ignore[misc]

        _IWebhook.send = webhook_send_with_default  # type: ignore[assignment]

    _patched = True
    logger.info("Registered default ephemeral=%s for interaction responses", _default_ephemeral)
