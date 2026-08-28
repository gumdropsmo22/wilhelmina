from __future__ import annotations

from dataclasses import dataclass

import pytest

from services import ai


@dataclass
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 4
    total_tokens: int = 14


class FakeResponse:
    output_text = "Done."
    model = "test-model"
    _request_id = "req_instructions"
    usage = FakeUsage()


class FakeAsyncResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeAsyncClient:
    def __init__(self) -> None:
        self.responses = FakeAsyncResponses()
        self.options: dict[str, object] = {}

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


@pytest.mark.asyncio
async def test_async_responses_forwards_optional_high_authority_instructions(monkeypatch):
    client = FakeAsyncClient()
    monkeypatch.setattr(ai, "_get_async_openai_client", lambda: client)
    config = ai.AIConfig(
        model="requested-model",
        timeout_seconds=5.0,
        max_retries=1,
        store_responses=False,
    )

    result = await ai.generate_result_async(
        "lower-authority input",
        instructions="developer authority",
        config=config,
        purpose="instruction_test",
    )

    assert result is not None
    assert client.responses.calls == [
        {
            "model": "requested-model",
            "input": "lower-authority input",
            "store": False,
            "instructions": "developer authority",
        }
    ]


@pytest.mark.asyncio
async def test_private_async_responses_preserves_store_false_with_instructions(monkeypatch):
    client = FakeAsyncClient()
    monkeypatch.setattr(ai, "_get_async_openai_client", lambda: client)
    policy = ai.AIPlatformPolicy(
        default_model="default",
        chat_model="chat-model",
        memory_model="memory-model",
        retention_mode="zdr",
    )

    result = await ai.generate_private_result_async(
        "authorized chat data",
        instructions="wilhelmina developer rules",
        workload="chat",
        purpose="chat_instruction_test",
        policy=policy,
    )

    assert result is not None
    assert client.responses.calls[0]["model"] == "chat-model"
    assert client.responses.calls[0]["input"] == "authorized chat data"
    assert client.responses.calls[0]["instructions"] == "wilhelmina developer rules"
    assert client.responses.calls[0]["store"] is False


@pytest.mark.asyncio
async def test_legacy_call_without_instructions_does_not_add_parameter(monkeypatch):
    client = FakeAsyncClient()
    monkeypatch.setattr(ai, "_get_async_openai_client", lambda: client)

    result = await ai.generate_result_async("legacy input", purpose="legacy_test")

    assert result is not None
    assert "instructions" not in client.responses.calls[0]
