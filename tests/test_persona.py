from services import persona


def test_feature_profile_routes_are_stable():
    assert persona.get_feature_profile("help").key == "help"
    assert persona.get_feature_profile("rules_intro").key == "rules_intro"
    assert persona.get_feature_profile("rules_acceptance").key == "rules_acceptance"
    assert persona.get_feature_profile("unknown").key == "help"


def test_prompt_includes_base_voice_feature_and_context_without_voice_channels():
    prompt = persona.build_prompt(
        feature_key="help",
        task="Write a grimoire intro.",
        context={"category": "Core", "visible_commands": "/about, /help"},
    )

    assert "Base voice" in prompt
    assert "cyber witch haunting a private Discord server" in prompt
    assert "hard boundary" in prompt
    assert "Feature:" in prompt
    assert "Voice channel" not in prompt
    assert "Write a grimoire intro." in prompt
    assert "visible_commands" in prompt
    assert "/about, /help" in prompt


def test_clean_persona_text_normalizes_and_clips():
    text = persona.clean_persona_text('"  The   house   listens.  "', max_chars=80)
    assert text == "The house listens."

    clipped = persona.clean_persona_text("abcdef", max_chars=4)
    assert clipped == "abc…"
