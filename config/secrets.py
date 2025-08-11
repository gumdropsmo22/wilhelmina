from __future__ import annotations
"""
Centralized env loader and getters.
Loads .env if present; never hardcode secrets.
"""
from dataclasses import dataclass
from typing import Optional
import os
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

_loaded = False

def load_env() -> None:
    global _loaded
    if _loaded:
        return
    if load_dotenv:
        load_dotenv()  # load .env into process env if present
    _loaded = True

@dataclass(frozen=True)
class Secrets:
    discord_token: Optional[str]
    openai_api_key: Optional[str]
    mongo_url: Optional[str]
    tz: Optional[str]

def get_secrets() -> Secrets:
    load_env()
    return Secrets(
        discord_token=os.getenv("DISCORD_TOKEN"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        mongo_url=os.getenv("MONGO_URL"),
        tz=os.getenv("TZ", "Asia/Riyadh"),
    )
