from __future__ import annotations

from dataclasses import dataclass

import pytest

from services import ai


@dataclass
class FakeUsage:
    input_tokens: int = 12
    output_tokens: int = 5
    total_tokens: int = 17


class FakeResponse:
    output_text = "First line\nSecond line"
    model = "test-model"
    _request_id = "req_test_123"
    usage = FakeUsage()


class FakeSyncResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeAsyncResponses:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.error = error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeResponse()


class FakeSyncClient:
    def __init__(self) -> None:
        self.responses = FakeSyncResponses()
        self.options: dict[str, object] = {}

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


class FakeAsyncClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.responses = FakeAsyncResponses(error=error)
        self.options: dict[str, object] = {}

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


def test_config_reads_privacy_timeout_and_retry_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "model-from-env")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "14.5")
    monkeypatch.setenv("AI_MAX_RETRIES", "3")
    monkeypatch.setenv("OPENAI_STORE_RESPONSES", "true")

    config = ai.AIConfig.from_env()

    assert config.model == "model-from-env"
    assert config.timeout_seconds == 14.5
    assert config.max_retries == 3
    assert config.store_responses is True


def test_config_rejects_negative_retries(monkeypatch):
    monkeypatch.setenv("AI_MAX_RETRIES", "-5")

    assert ai.AIConfig.from_env().max_retries == 0


def test_ai_available_requires_sdk_and_key(monkeypatch):
    monkeypatch.setattr(ai, "OpenAI", object())
    monkeypatch.setattr(ai, "AsyncOpenAI", object())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert ai.ai_available() is False

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert ai.ai_available() is True


def test_generate_result_returns_safe_metadata(monkeypatch):
    client = FakeSyncClient()
    monkeypatch.setattr(ai, "_get_sync_openai_client", lambda: client)
    config = ai.AIConfig(
        model="requested-model",
        timeout_seconds=4.0,
        max_retries=2,
        store_responses=False,
    )

    result = ai.generate_result("Say hello", config=config, purpose="unit_test")

    assert result is not None
    assert result.text == "First line Second line"
    assert result.model == "test-model"
    assert result.request_id == "req_test_123"
    assert result.input_tokens == 12
    assert result.output_tokens == 5
    assert result.total_tokens == 17
    assert client.options == {"timeout": 4.0, "max_retries": 2}
    assert client.responses.calls == [
        {
            "model": "requested-model",
            "input": "Say hello",
            "store": False,
        }
    ]


@pytest.mark.asyncio
async def test_generate_result_async_uses_native_async_client(monkeypatch):
    client = FakeAsyncClient()
    monkeypatch.setattr(ai, "_get_async_openai_client", lambda: client)
    config = ai.AIConfig(
        model="requested-model",
        timeout_seconds=6.0,
        max_retries=1,
        store_responses=False,
    )

    result = await ai.generate_result_async(
        "Say hello",
        config=config,
        preserve_newlines=True,
        purpose="unit_test",
    )

    assert result is not None
    assert result.text == "First line\nSecond line"
    assert client.options == {"timeout": 6.0, "max_retries": 1}
    assert client.responses.calls[0]["store"] is False


@pytest.mark.asyncio
async def test_async_failure_returns_none_without_raising(monkeypatch):
    client = FakeAsyncClient(error=RuntimeError("boom"))
    monkeypatch.setattr(ai, "_get_async_openai_client", lambda: client)

    result = await ai.generate_result_async("Say hello", purpose="unit_test")

    assert result is None


@pytest.mark.asyncio
async def test_generate_text_async_preserves_existing_string_contract(monkeypatch):
    client = FakeAsyncClient()
    monkeypatch.setattr(ai, "_get_async_openai_client", lambda: client)

    text = await ai.generate_text_async("Say hello")
    markdown = await ai.generate_markdown_async("Say hello")

    assert text == "First line Second line"
    assert markdown == "First line\nSecond line"
