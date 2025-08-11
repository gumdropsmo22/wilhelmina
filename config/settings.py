from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class Settings:
    discord_token: str | None
    embeds_only: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            discord_token=os.getenv("DISCORD_TOKEN"),
            embeds_only=True,
        )
