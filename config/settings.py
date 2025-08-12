import os
from pathlib import Path
from dotenv import load_dotenv

# load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

APP_ENV      = os.getenv("APP_ENV", "development")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")
DISCORD_TOKEN= os.getenv("DISCORD_TOKEN")
LOG_LEVEL    = os.getenv("LOG_LEVEL", "INFO")

def require_token() -> str:
    if not DISCORD_TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    return DISCORD_TOKEN
