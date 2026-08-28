from __future__ import annotations

from types import SimpleNamespace

from bot import build_intents


def _settings(*, rules: bool = False, extraction: bool = False, chat: bool = False):
    enabled = {
        "cogs.rules": rules,
        "cogs.memory_extraction": extraction,
        "cogs.chat": chat,
    }
    return SimpleNamespace(is_cog_enabled=lambda extension: enabled.get(extension, False))


def test_message_content_intent_stays_off_when_chat_and_extractor_are_disabled():
    intents = build_intents(_settings(extraction=False, chat=False))
    assert intents.message_content is False


def test_extractor_explicitly_enables_message_content_intent():
    intents = build_intents(_settings(extraction=True, chat=False))
    assert intents.message_content is True


def test_chat_explicitly_enables_message_content_intent_without_extraction():
    intents = build_intents(_settings(extraction=False, chat=True))
    assert intents.message_content is True


def test_rules_member_intent_is_independent_from_chat_and_extraction():
    intents = build_intents(_settings(rules=True, extraction=False, chat=False))
    assert intents.members is True
    assert intents.message_content is False
