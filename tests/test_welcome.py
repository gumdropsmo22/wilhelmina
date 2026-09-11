from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from bot import build_intents
from cogs import welcome as welcome_cog
from config import settings as settings_module
from services.database import initialize_database, managed_connection
from services.guild_config import set_channel
from services.persona import fallback_for
from services.welcome import format_welcome_message


class DummyTextChannel:
    def __init__(self, channel_id: int):
        self.id = channel_id
        self.sent: list[tuple[str, dict[str, object]]] = []

    async def send(self, content: str, **kwargs) -> None:
        self.sent.append((content, kwargs))


class DummyBot:
    def __init__(self, *, database_path, home_guild_id: int, channels=None):
        self.settings = SimpleNamespace(
            database_path=database_path,
            home_guild_id=home_guild_id,
        )
        self._channels = channels or {}

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)


class DummyMember:
    def __init__(self, *, guild_id: int = 123, user_id: int = 42, bot: bool = False):
        self.guild = SimpleNamespace(id=guild_id)
        self.id = user_id
        self.bot = bot
        self.display_name = "Mina"
        self.mention = f"<@{user_id}>"


def _load_settings(values: dict[str, str]):
    with mock.patch.object(settings_module, "load_dotenv", lambda *args, **kwargs: None):
        with mock.patch.dict("os.environ", values, clear=True):
            return settings_module.load_settings()


def _intent_settings(*, welcome: bool, rules: bool = False):
    enabled = {
        "cogs.rules": rules,
        "cogs.welcome": welcome,
        "cogs.memory_extraction": False,
        "cogs.chat": False,
    }
    return SimpleNamespace(is_cog_enabled=lambda extension: enabled.get(extension, False))


def test_welcome_feature_flag_defaults_off_and_can_be_enabled():
    disabled = _load_settings(
        {
            "DISCORD_TOKEN": "token",
            "COMMAND_SYNC_MODE": "off",
        }
    )
    enabled = _load_settings(
        {
            "DISCORD_TOKEN": "token",
            "COMMAND_SYNC_MODE": "off",
            "ENABLE_WELCOME": "true",
        }
    )

    assert disabled.is_cog_enabled("cogs.welcome") is False
    assert enabled.is_cog_enabled("cogs.welcome") is True


def test_welcome_enables_members_intent_without_rules():
    intents = build_intents(_intent_settings(welcome=True, rules=False))
    assert intents.members is True
    assert intents.message_content is False


def test_format_welcome_message_keeps_target_outside_generated_copy():
    assert format_welcome_message(member_mention="<@42>", text="Step inside.") == (
        "<@42> — Step inside."
    )


@pytest.mark.asyncio
async def test_join_posts_generated_welcome_to_configured_channel(tmp_path, monkeypatch):
    database = tmp_path / "welcome.sqlite3"
    initialize_database(database)
    with managed_connection(database) as connection:
        set_channel(connection, 123, "welcome_channel_id", 789)

    channel = DummyTextChannel(789)
    bot = DummyBot(database_path=database, home_guild_id=123, channels={789: channel})
    member = DummyMember()

    monkeypatch.setattr(welcome_cog.discord, "TextChannel", DummyTextChannel)

    async def fake_welcome(*, display_name: str) -> str:
        assert display_name == "Mina"
        return "Step inside, darling. The house has already judged the shoes."

    monkeypatch.setattr(welcome_cog, "build_welcome_text", fake_welcome)

    await welcome_cog.WelcomeCog(bot).on_member_join(member)

    assert len(channel.sent) == 1
    content, kwargs = channel.sent[0]
    assert content == (
        "<@42> — Step inside, darling. The house has already judged the shoes."
    )
    assert "allowed_mentions" in kwargs


@pytest.mark.asyncio
async def test_join_uses_fallback_when_persona_generation_fails(tmp_path, monkeypatch):
    database = tmp_path / "welcome.sqlite3"
    initialize_database(database)
    with managed_connection(database) as connection:
        set_channel(connection, 123, "welcome_channel_id", 789)

    channel = DummyTextChannel(789)
    bot = DummyBot(database_path=database, home_guild_id=123, channels={789: channel})
    member = DummyMember()

    monkeypatch.setattr(welcome_cog.discord, "TextChannel", DummyTextChannel)

    async def broken_welcome(*, display_name: str) -> str:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(welcome_cog, "build_welcome_text", broken_welcome)

    await welcome_cog.WelcomeCog(bot).on_member_join(member)

    assert channel.sent[0][0] == f"<@42> — {fallback_for('welcome')}"


@pytest.mark.asyncio
async def test_join_is_silent_when_welcome_channel_is_unconfigured(tmp_path, monkeypatch):
    database = tmp_path / "welcome.sqlite3"
    initialize_database(database)

    channel = DummyTextChannel(789)
    bot = DummyBot(database_path=database, home_guild_id=123, channels={789: channel})
    member = DummyMember()
    monkeypatch.setattr(welcome_cog.discord, "TextChannel", DummyTextChannel)

    await welcome_cog.WelcomeCog(bot).on_member_join(member)

    assert channel.sent == []


@pytest.mark.asyncio
async def test_join_ignores_bots_and_other_guilds(tmp_path):
    database = tmp_path / "welcome.sqlite3"
    bot = DummyBot(database_path=database, home_guild_id=123)
    cog = welcome_cog.WelcomeCog(bot)

    await cog.on_member_join(DummyMember(bot=True))
    await cog.on_member_join(DummyMember(guild_id=999))

    assert not database.exists()
