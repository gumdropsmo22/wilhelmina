import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from config import secrets


def test_env_loader_smoke():
    s = secrets.get_secrets()
    assert hasattr(s, "discord_token")
    assert hasattr(s, "openai_api_key")
    assert hasattr(s, "mongo_url")
    assert hasattr(s, "tz")
