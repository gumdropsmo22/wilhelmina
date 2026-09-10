from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from cogs.tarot import Tarot
from services import help as help_service


def test_tarot_feature_flag_exists_and_defaults_off(monkeypatch):
    monkeypatch.delenv("ENABLE_TAROT", raising=False)
    enabled = settings._read_enabled_cogs()
    assert enabled["cogs.tarot"] is False
    flag = next(flag for flag in settings.COG_FLAGS if flag.extension == "cogs.tarot")
    assert flag.env_var == "ENABLE_TAROT"
    assert flag.default_enabled is False


def test_tarot_is_divination_and_not_coming_soon():
    assert help_service.DEFAULT_CATEGORY_MAP["tarot"] == "divination"
    assert "/tarot" not in help_service.COMING_SOON["divination"]


def test_tarot_group_exposes_single_and_three_commands():
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    cog = Tarot(bot)
    commands_by_name = {command.name: command for command in cog.get_app_commands()}
    assert set(commands_by_name) == {"tarot"}
    group = commands_by_name["tarot"]
    assert isinstance(group, app_commands.Group)
    assert {command.name for command in group.commands} == {"single", "three"}
