from __future__ import annotations

from unittest import mock

from config import settings as settings_module
from services import persona


def _load_with_env(values):
    with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
        with mock.patch.dict("os.environ", values, clear=True):
            return settings_module.load_settings()


def test_chat_is_disabled_by_default():
    loaded = _load_with_env(
        {
            "DISCORD_TOKEN": "token",
            "COMMAND_SYNC_MODE": "off",
        }
    )
    assert loaded.is_cog_enabled("cogs.chat") is False


def test_chat_can_be_enabled_independently_from_memory_extraction():
    loaded = _load_with_env(
        {
            "DISCORD_TOKEN": "token",
            "COMMAND_SYNC_MODE": "off",
            "ENABLE_CHAT": "true",
            "ENABLE_MEMORY_EXTRACTION": "false",
        }
    )
    assert loaded.is_cog_enabled("cogs.chat") is True
    assert loaded.is_cog_enabled("cogs.memory_extraction") is False


def test_chat_has_an_explicit_persona_profile():
    profile = persona.get_feature_profile("chat")
    assert profile.key == "chat"
    assert profile.label == "Chat"
    assert profile.max_chars == 1900
    assert persona.fallback_for("chat")
