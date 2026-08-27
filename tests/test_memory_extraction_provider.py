from __future__ import annotations

from types import SimpleNamespace

import pytest

from services import ai, memory_extraction_provider


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output_text='{"candidates":[]}',
            model="memory-model",
            _request_id="req_123",
            usage=SimpleNamespace(input_tokens=10, output_tokens=4, total_tokens=14),
        )


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()
        self.options = None

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


@pytest.mark.asyncio
async def test_structured_provider_uses_strict_schema_and_store_false(monkeypatch):
    client = FakeClient()
    config = ai.AIConfig(
        model="memory-model",
        timeout_seconds=9.0,
        max_retries=2,
        store_responses=False,
    )
    monkeypatch.setattr(ai, "private_ai_config", lambda **kwargs: config)
    monkeypatch.setattr(ai, "_get_async_openai_client", lambda: client)

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidates"],
        "properties": {"candidates": {"type": "array", "items": {"type": "string"}}},
    }
    result = await memory_extraction_provider.extract_structured(
        instructions="extract",
        input_text="message data",
        schema_name="memory_test",
        schema=schema,
    )

    assert result is not None
    assert result.payload == {"candidates": []}
    assert result.request_id == "req_123"
    assert result.total_tokens == 14
    assert client.options == {"timeout": 9.0, "max_retries": 2}
    assert client.responses.kwargs["model"] == "memory-model"
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["text"]["format"] == {
        "type": "json_schema",
        "name": "memory_test",
        "schema": schema,
        "strict": True,
    }


def test_provider_ready_requires_api_and_private_retention(monkeypatch):
    monkeypatch.setattr(ai, "ai_available", lambda: False)
    assert memory_extraction_provider.provider_ready() is False

    monkeypatch.setattr(ai, "ai_available", lambda: True)
    monkeypatch.setattr(
        ai,
        "private_ai_config",
        lambda **kwargs: (_ for _ in ()).throw(ai.AIPrivacyConfigurationError("blocked")),
    )
    assert memory_extraction_provider.provider_ready() is False
