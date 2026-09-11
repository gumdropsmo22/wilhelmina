from __future__ import annotations

from types import SimpleNamespace

import pytest

from cogs import tarot as tarot_cog
from services import tarot


class FakeResponse:
    def __init__(self):
        self.deferred = []
        self.sent = []

    async def defer(self, *, ephemeral=False):
        self.deferred.append(ephemeral)

    async def send_message(self, content, *, ephemeral=False):
        self.sent.append((content, ephemeral))


class FakeFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)


class FakeInteraction:
    def __init__(self):
        self.response = FakeResponse()
        self.followup = FakeFollowup()


def _reading(*, question=None):
    return tarot.TarotReading(
        spread=tarot.SpreadKind.SINGLE,
        cards=(tarot.DrawnCard("Card", tarot.CARD_BY_ID["major_00_the_fool"], tarot.Orientation.UPRIGHT),),
        question=question,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("visibility", "expected"), [("public", False), ("private", True)])
async def test_visibility_controls_defer_and_followup(monkeypatch, visibility, expected):
    reading = _reading()
    monkeypatch.setattr(tarot_cog.tarot, "draw_reading", lambda *args, **kwargs: reading)

    async def fake_interpret(value):
        return tarot.TarotInterpretation(text="The Fool says move.", provider_used=False, fallback_reason="test")

    monkeypatch.setattr(tarot_cog.tarot, "generate_interpretation", fake_interpret)
    monkeypatch.setattr(tarot_cog, "_artwork_payload", lambda value: ([], []))
    cog = tarot_cog.Tarot(SimpleNamespace())
    interaction = FakeInteraction()
    await cog._run(interaction, spread=tarot.SpreadKind.SINGLE, visibility=visibility, question=None)
    assert interaction.response.deferred == [expected]
    assert interaction.followup.sent[0]["ephemeral"] is expected


@pytest.mark.asyncio
async def test_rejected_question_is_private_and_does_not_defer(monkeypatch):
    def rejected(*args, **kwargs):
        raise tarot.TarotQuestionRejected("Ask the cards without including credentials or secrets.")

    monkeypatch.setattr(tarot_cog.tarot, "draw_reading", rejected)
    cog = tarot_cog.Tarot(SimpleNamespace())
    interaction = FakeInteraction()
    await cog._run(interaction, spread=tarot.SpreadKind.THREE, visibility="public", question="secret")
    assert interaction.response.deferred == []
    assert interaction.followup.sent == []
    assert interaction.response.sent == [("Ask the cards without including credentials or secrets.", True)]


def test_reading_embed_preserves_card_and_orientation():
    embed = tarot_cog._reading_embed(_reading(), tarot.TarotInterpretation(text="Move.", provider_used=True))
    assert embed.title == "▒▒ TAROT • SINGLE CARD ▒▒"
    assert embed.description == "Move."
    assert "The Fool" in embed.fields[0].name
    assert "Upright" in embed.fields[0].value


def test_reading_embed_clips_only_displayed_long_question():
    question = "q" * 2000
    reading = _reading(question=question)
    embed = tarot_cog._reading_embed(reading, tarot.TarotInterpretation(text="Move.", provider_used=True))
    assert reading.question == question
    assert len(embed.fields[0].value) == tarot_cog.EMBED_FIELD_VALUE_LIMIT
    assert embed.fields[0].value.endswith("…")
