from __future__ import annotations

from dataclasses import dataclass

import pytest

from services import ai, tarot


@dataclass
class FakeRng:
    selected_ids: tuple[str, ...]
    bits: tuple[int, ...]

    def __post_init__(self) -> None:
        self._bit_index = 0

    def sample(self, population, k):
        by_id = {card.card_id: card for card in population}
        return [by_id[card_id] for card_id in self.selected_ids[:k]]

    def getrandbits(self, k):
        assert k == 1
        value = self.bits[self._bit_index]
        self._bit_index += 1
        return value


def test_deck_is_standard_78_card_shape():
    assert len(tarot.DECK) == 78
    assert len({card.card_id for card in tarot.DECK}) == 78
    assert len({card.name for card in tarot.DECK}) == 78
    assert sum(card.arcana == "major" for card in tarot.DECK) == 22
    assert sum(card.arcana == "minor" for card in tarot.DECK) == 56


def test_minor_arcana_has_four_complete_suits():
    for suit in ("wands", "cups", "swords", "pentacles"):
        assert len([card for card in tarot.DECK if card.suit == suit]) == 14


def test_three_card_draw_is_unique_positioned_and_reversed_independently():
    rng = FakeRng(("major_16_the_tower", "cups_two", "swords_ace"), (0, 1, 1))
    reading = tarot.draw_reading(tarot.SpreadKind.THREE, question="Where is this going?", rng=rng)
    assert [card.position for card in reading.cards] == ["Past", "Present", "Future"]
    assert len({card.card.card_id for card in reading.cards}) == 3
    assert [card.orientation for card in reading.cards] == [tarot.Orientation.UPRIGHT, tarot.Orientation.REVERSED, tarot.Orientation.REVERSED]


def test_single_card_draw_supports_general_reading():
    reading = tarot.draw_reading(tarot.SpreadKind.SINGLE, rng=FakeRng(("major_09_the_hermit",), (1,)))
    assert reading.question is None
    assert len(reading.cards) == 1
    assert reading.cards[0].position == "Card"
    assert reading.cards[0].orientation is tarot.Orientation.REVERSED


def test_question_rejects_concrete_credentials():
    with pytest.raises(tarot.TarotQuestionRejected):
        tarot.normalize_question("my password is purplemonkey")


def test_provider_request_freezes_exact_draw():
    reading = tarot.draw_reading(tarot.SpreadKind.THREE, question="What changes next?", rng=FakeRng(("major_13_death", "major_17_the_star", "cups_ace"), (0, 1, 0)))
    request = tarot.build_provider_request(reading)
    assert '"name":"Death"' in request.input
    assert '"name":"The Star"' in request.input
    assert '"orientation":"reversed"' in request.input
    assert "Never redraw, replace, reorder, add, remove, or flip a card." in request.instructions


@pytest.mark.asyncio
async def test_ai_interprets_frozen_draw(monkeypatch):
    reading = tarot.draw_reading(tarot.SpreadKind.SINGLE, question="What am I walking into?", rng=FakeRng(("major_00_the_fool",), (0,)))
    captured = {}

    async def fake_generate(input_text, **kwargs):
        captured["input"] = input_text
        captured.update(kwargs)
        return ai.AIResult(text="**The Fool — Upright**\nMove, but look where you put your feet.", model="test-model", request_id="req_tarot", input_tokens=1, output_tokens=1, total_tokens=2)

    monkeypatch.setattr(tarot.ai, "generate_private_result_async", fake_generate)
    result = await tarot.generate_interpretation(reading)
    assert result.provider_used is True
    assert captured["workload"] == "default"
    assert captured["require_enhanced_retention"] is False
    assert '"card_id":"major_00_the_fool"' in captured["input"]


@pytest.mark.asyncio
async def test_provider_failure_keeps_draw_and_returns_local_fallback(monkeypatch):
    reading = tarot.draw_reading(tarot.SpreadKind.SINGLE, question="What am I avoiding?", rng=FakeRng(("major_09_the_hermit",), (1,)))
    async def unavailable(*args, **kwargs):
        return None
    monkeypatch.setattr(tarot.ai, "generate_private_result_async", unavailable)
    result = await tarot.generate_interpretation(reading)
    assert result.provider_used is False
    assert result.fallback_reason == "provider_unavailable"
    assert "The Hermit" in result.text
    assert "Reversed" in result.text
    assert "isolation" in result.text
