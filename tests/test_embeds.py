from utils.embeds import system_embed, build_embed


def test_system_embed_minimal():
    e = system_embed(header="▒▒ TEST ▒▒", description="hello", include_trace=False)
    assert e.title == "▒▒ TEST ▒▒"
    assert "hello" in (e.description or "")
    assert e.author
    assert e.footer
    assert e.colour.value == 0x6E00FF


def test_system_embed_trace_field_present():
    e = system_embed(header="t", description="d", include_trace=True)
    assert len(e.fields) >= 1


def test_build_embed_minimal():
    e = build_embed(title="t", description="d")
    assert e.title == "t"
    assert "d" in (e.description or "")
    assert e.colour.value == 0x6E00FF
