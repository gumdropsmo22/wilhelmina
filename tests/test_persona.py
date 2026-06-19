from services import persona


def test_voice_channel_routes_are_stable():
    assert persona.get_voice_channel("help").key == "guide"
    assert persona.get_voice_channel("rules_intro").key == "ritual"
    assert persona.get_voice_channel("rules_acceptance").key == "ritual"


def test_prompt_includes_base_voice_channel_and_context():
    prompt = persona.build_prompt(
        feature_key="help",
        task="Write a grimoire intro.",
        context={"category": "Core", "visible_commands": "/about, /help"},
    )

    assert "Base voice" in prompt
    assert "Voice channel: Guide" in prompt
    assert "Write a grimoire intro." in prompt
    assert "visible_commands" in prompt
    assert "/about, /help" in prompt


def test_clean_persona_text_normalizes_and_clips():
    text = persona.clean_persona_text('"  The   house   listens.  "', max_chars=80)
    assert text == "The house listens."

    clipped = persona.clean_persona_text("abcdef", max_chars=4)
    assert clipped == "abc…"
