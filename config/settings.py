from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}
VALID_COMMAND_SYNC_MODES = {"guild", "dev", "global", "off", "auto"}
VALID_SERVER_MODES = {"dedicated"}


class SettingsError(RuntimeError):
    """Raised when Wilhelmina runtime configuration is missing or invalid."""


@dataclass(frozen=True)
class CogFlag:
    """Declarative switch for one Discord extension/cog."""

    extension: str
    env_var: str
    default_enabled: bool
    description: str
    required: bool = False


@dataclass(frozen=True)
class RuntimeSettings:
    """Validated runtime settings for Wilhelmina."""

    discord_token: str
    client_id: str | None
    app_env: str
    server_mode: str
    home_guild_id: int | None
    log_level: str
    command_sync_mode: str
    cog_flags: tuple[CogFlag, ...]
    enabled_cogs: Mapping[str, bool]

    def is_cog_enabled(self, extension: str) -> bool:
        return bool(self.enabled_cogs.get(extension, False))


COG_FLAGS: tuple[CogFlag, ...] = (
    CogFlag(
        extension="cogs.core",
        env_var="ENABLE_CORE",
        default_enabled=True,
        description="Core commands and runtime health checks.",
        required=True,
    ),
    CogFlag(
        extension="cogs.admin",
        env_var="ENABLE_ADMIN",
        default_enabled=True,
        description="Admin diagnostics and runtime inspection commands.",
        required=True,
    ),
    CogFlag(
        extension="cogs.invite",
        env_var="ENABLE_INVITE",
        default_enabled=False,
        description="Invite-link command and Discord authorization helper.",
    ),
    CogFlag(
        extension="cogs.roll",
        env_var="ENABLE_ROLL",
        default_enabled=False,
        description="Dice rolling command with number lore.",
    ),
    CogFlag(
        extension="cogs.eight_ball",
        env_var="ENABLE_EIGHT_BALL",
        default_enabled=False,
        description="Magic 8-Ball question command.",
    ),
    CogFlag(
        extension="cogs.fortune",
        env_var="ENABLE_FORTUNE",
        default_enabled=False,
        description="Fortune-cookie style generated message command.",
    ),
)


def _load_env() -> None:
    """Load .env from the repository root if it exists."""

    load_dotenv(dotenv_path=ENV_PATH)


def _get_str(name: str, *, default: str | None = None, required: bool = False) -> str | None:
    value = os.getenv(name)

    if value is None:
        if required:
            raise SettingsError(f"Missing required environment variable: {name}")
        return default

    value = value.strip()

    if required and not value:
        raise SettingsError(f"Missing required environment variable: {name}")

    return value if value else default


def _get_int(name: str, *, default: int | None = None, required: bool = False) -> int | None:
    raw = _get_str(name, default=None, required=required)

    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise SettingsError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def _get_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)

    if raw is None or raw.strip() == "":
        return default

    value = raw.strip().lower()

    if value in TRUE_VALUES:
        return True

    if value in FALSE_VALUES:
        return False

    raise SettingsError(
        f"Environment variable {name} must be a boolean "
        f"(true/false, yes/no, on/off, 1/0), got {raw!r}"
    )


def _get_bool_or_default(name: str, *, default: bool = False) -> bool:
    """Read a boolean for compatibility globals without failing module import."""

    try:
        return _get_bool(name, default=default)
    except SettingsError:
        return default


def _get_home_guild_id() -> int | None:
    """Return the dedicated server guild ID, accepting DEV_GUILD_ID as a legacy alias."""

    home_guild_id = _get_int("HOME_GUILD_ID", default=None)
    if home_guild_id is not None:
        return home_guild_id

    return _get_int("DEV_GUILD_ID", default=None)


def _get_command_sync_mode() -> str:
    mode = (_get_str("COMMAND_SYNC_MODE", default="guild") or "guild").lower()

    if mode not in VALID_COMMAND_SYNC_MODES:
        raise SettingsError(
            f"COMMAND_SYNC_MODE must be one of {sorted(VALID_COMMAND_SYNC_MODES)}, got {mode!r}"
        )

    if mode == "dev":
        return "guild"

    return mode


def _get_command_sync_mode_or_default() -> str:
    """Read command sync mode for compatibility globals without failing module import."""

    try:
        return _get_command_sync_mode()
    except SettingsError:
        return "guild"


def _get_server_mode() -> str:
    mode = (_get_str("SERVER_MODE", default="dedicated") or "dedicated").lower()

    if mode not in VALID_SERVER_MODES:
        raise SettingsError(
            "SERVER_MODE must be 'dedicated'. Server takeover/transformation modes are not supported."
        )

    return mode


def _read_enabled_cogs() -> Mapping[str, bool]:
    enabled = {
        flag.extension: _get_bool(flag.env_var, default=flag.default_enabled)
        for flag in COG_FLAGS
    }

    # Compatibility shim: old ENABLE_ORACLES=true enables the three old commands, but the
    # runtime no longer loads cogs.oracles. This keeps old .env files from going silent.
    if _get_bool("ENABLE_ORACLES", default=False):
        enabled = dict(enabled)
        enabled["cogs.roll"] = True
        enabled["cogs.eight_ball"] = True
        enabled["cogs.fortune"] = True

    disabled_required = [
        flag.env_var
        for flag in COG_FLAGS
        if flag.required and not enabled.get(flag.extension, False)
    ]

    if disabled_required:
        joined = ", ".join(disabled_required)
        raise SettingsError(f"Required cog flag cannot be disabled: {joined}")

    return MappingProxyType(enabled)


def load_settings() -> RuntimeSettings:
    """Load and validate Wilhelmina runtime settings."""

    _load_env()

    discord_token = _get_str("DISCORD_TOKEN", required=True)
    client_id = _get_str("CLIENT_ID", default=None)
    app_env = _get_str("APP_ENV", default="development") or "development"
    server_mode = _get_server_mode()
    home_guild_id = _get_home_guild_id()
    log_level = (_get_str("LOG_LEVEL", default="INFO") or "INFO").upper()
    command_sync_mode = _get_command_sync_mode()

    if command_sync_mode == "guild" and home_guild_id is None:
        raise SettingsError(
            "HOME_GUILD_ID is required when COMMAND_SYNC_MODE=guild "
            "(DEV_GUILD_ID is accepted as a legacy alias)."
        )

    return RuntimeSettings(
        discord_token=discord_token,
        client_id=client_id,
        app_env=app_env,
        server_mode=server_mode,
        home_guild_id=home_guild_id,
        log_level=log_level,
        command_sync_mode=command_sync_mode,
        cog_flags=COG_FLAGS,
        enabled_cogs=_read_enabled_cogs(),
    )


def require_token() -> str:
    """Compatibility helper for modules that need only the Discord token."""

    return load_settings().discord_token


def is_feature_enabled(extension: str) -> bool:
    """Return whether a known cog extension is enabled by environment flags."""

    return bool(_read_enabled_cogs().get(extension, False))


_load_env()

APP_ENV = _get_str("APP_ENV", default="development") or "development"
SERVER_MODE = _get_str("SERVER_MODE", default="dedicated") or "dedicated"
HOME_GUILD_ID = _get_str("HOME_GUILD_ID", default=_get_str("DEV_GUILD_ID", default=None))
DEV_GUILD_ID = HOME_GUILD_ID
CLIENT_ID = _get_str("CLIENT_ID", default=None)
DISCORD_TOKEN = _get_str("DISCORD_TOKEN", default=None)
LOG_LEVEL = (_get_str("LOG_LEVEL", default="INFO") or "INFO").upper()
COMMAND_SYNC_MODE = _get_command_sync_mode_or_default()

ENABLE_CORE = _get_bool_or_default("ENABLE_CORE", default=True)
ENABLE_ADMIN = _get_bool_or_default("ENABLE_ADMIN", default=True)
ENABLE_INVITE = _get_bool_or_default("ENABLE_INVITE", default=False)
ENABLE_ROLL = _get_bool_or_default("ENABLE_ROLL", default=False)
ENABLE_EIGHT_BALL = _get_bool_or_default("ENABLE_EIGHT_BALL", default=False)
ENABLE_FORTUNE = _get_bool_or_default("ENABLE_FORTUNE", default=False)

# Legacy flag retained only as a compatibility shim. Do not use for new configuration.
ENABLE_ORACLES = _get_bool_or_default("ENABLE_ORACLES", default=False)

EMBEDS_ONLY = _get_bool_or_default("EMBEDS_ONLY", default=True)
