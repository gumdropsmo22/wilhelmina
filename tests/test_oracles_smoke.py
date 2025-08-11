from utils.embeds import build_embed
from utils.persona import say
import json, pathlib

def test_build_embed_minimal():
    e = build_embed(title="t", description="d")
    assert e.title == "t"
    assert "d" in (e.description or "")

def test_persona_say_nonempty():
    s = say()
    assert isinstance(s, str) and len(s) > 0

def test_data_files_exist():
    p = pathlib.Path("data/fortunes.json")
    j = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(j, list) and len(j) >= 10
