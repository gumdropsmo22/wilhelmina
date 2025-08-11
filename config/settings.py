from __future__ import annotations
import os
from dataclasses import dataclass
from . import secrets

@dataclass
class Settings:
    discord_token: str | None
    embeds_only: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        s = secrets.get_secrets()
        return cls(
            discord_token=s.discord_token,
            embeds_only=True,
        )
