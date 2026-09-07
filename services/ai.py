from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

try:
    import openai
    from openai import AsyncOpenAI, OpenAI
except ImportError:  # pragma: no cover - optional dependency guard
    openai = None
    AsyncOpenAI = None
    OpenAI = None

logger = logging.getLogger("wilhelmina.ai")

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_CHAT_MODEL = "gpt-5.6-sol"
DEFAULT_MEMORY_MODEL = "gpt-5.6-terra"
VALID_RETENTION_MODES = frozenset({"standard", "mam", "zdr"})
VALID_WORKLOADS = frozenset({"default", "chat", "memory"})


class AIPrivacyConfigurationError(RuntimeError):
    """Raised when a private OpenAI call would violate Wilhelmina's privacy contract."""


@dataclass(frozen=True)
class AIConfig:
    """Runtime configuration shared by Wilhelmina's OpenAI-backed features."""

    model: str = DEFAULT_MODEL
    timeout_seconds: float = 8.0
    max_retries: int = 1
    store_responses: bool = False

    @classmethod
    def from_env(cls) -> "AIConfig":
        return cls(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            timeout_seconds=_read_float("AI_TIMEOUT_SECONDS", default=8.0),
            max_retries=max(0, _read_int("AI_MAX_RETRIES", default=1)),
            store_responses=_read_bool("OPENAI_STORE_RESPONSES", default=False),
        )


@dataclass(frozen=True)
class AIPlatformPolicy:
    """Model routing and provider-retention assertions for private Wilhelmina features."""

    default_model: str = DEFAULT_MODEL
    chat_model: str = DEFAULT_CHAT_MODEL
    memory_model: str = DEFAULT_MEMORY_MODEL
    retention_mode: str = "standard"

    @classmethod
    def from_env(cls) -> "AIPlatformPolicy":
        base = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        chat = os.getenv("OPENAI_CHAT_MODEL", DEFAULT_CHAT_MODEL).strip() or DEFAULT_CHAT_MODEL
        memory = (
            os.getenv("OPENAI_MEMORY_MODEL", DEFAULT_MEMORY_MODEL).strip()
            or DEFAULT_MEMORY_MODEL
        )
        retention = (os.getenv("OPENAI_RETENTION_MODE", "standard").strip() or "standard").lower()
        if retention not in VALID_RETENTION_MODES:
            allowed = ", ".join(sorted(VALID_RETENTION_MODES))
            raise AIPrivacyConfigurationError(
                f"OPENAI_RETENTION_MODE must be one of: {allowed}"
            )
        return cls(
            default_model=base,
            chat_model=chat,
            memory_model=memory,
            retention_mode=retention,
        )

    @property
    def enhanced_retention(self) -> bool:
        """Return whether MAM or ZDR has been explicitly configured for the project."""

        return self.retention_mode in {"mam", "zdr"}

    def model_for(self, workload: str) -> str:
        normalized = workload.strip().lower()
        if normalized not in VALID_WORKLOADS:
            allowed = ", ".join(sorted(VALID_WORKLOADS))
            raise ValueError(f"Unknown AI workload {workload!r}; expected one of: {allowed}")
        if normalized == "chat":
            return self.chat_model
        if normalized == "memory":
            return self.memory_model
        return self.default_model


@dataclass(frozen=True)
class AIResult:
    """Safe metadata returned from one successful OpenAI response."""

    text: str
    model: str
    request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


_sync_client: Any | None = None
_async_client: Any | None = None


def _read_float(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid_float_setting name=%s default=%s", name, default)
        return default


def _read_int(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid_int_setting name=%s default=%s", name, default)
        return default


def _read_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    logger.warning("invalid_bool_setting name=%s default=%s", name, default)
    return default


def private_ai_config(
    *,
    workload: str,
    policy: AIPlatformPolicy | None = None,
    require_enhanced_retention: bool = True,
) -> AIConfig:
    """Build a fail-closed config for memory-aware/private Discord content.

    Provider-side MAM/ZDR is configured outside the request itself. This helper makes
    that deployment assertion explicit and always forces Responses API storage off.
    """

    policy = policy or AIPlatformPolicy.from_env()
    if require_enhanced_retention and not policy.enhanced_retention:
        raise AIPrivacyConfigurationError(
            "Private Wilhelmina OpenAI calls require OPENAI_RETENTION_MODE=mam or zdr"
        )
    base = AIConfig.from_env()
    return AIConfig(
        model=policy.model_for(workload),
        timeout_seconds=base.timeout_seconds,
        max_retries=base.max_retries,
        store_responses=False,
    )


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def ai_available() -> bool:
    """Return whether the OpenAI SDK and an API key are available."""

    return OpenAI is not None and AsyncOpenAI is not None and _has_api_key()


def _get_sync_openai_client() -> Any | None:
    global _sync_client

    if not ai_available():
        return None
    if _sync_client is not None:
        return _sync_client

    try:
        _sync_client = OpenAI()
    except Exception as exc:  # pragma: no cover - SDK construction failure is environment-specific
        _log_failure(exc, purpose="client_init", model=None)
        return None
    return _sync_client


def _get_async_openai_client() -> Any | None:
    global _async_client

    if not ai_available():
        return None
    if _async_client is not None:
        return _async_client

    try:
        _async_client = AsyncOpenAI()
    except Exception as exc:  # pragma: no cover - SDK construction failure is environment-specific
        _log_failure(exc, purpose="async_client_init", model=None)
        return None
    return _async_client


def _reset_clients_for_tests() -> None:
    """Clear cached SDK clients. Tests only; runtime code should not call this."""

    global _sync_client, _async_client
    _sync_client = None
    _async_client = None


def _normalize_text(value: str, *, preserve_newlines: bool) -> str:
    text = value.strip()
    if preserve_newlines:
        return text
    return text.replace("\n", " ")


def _usage_value(usage: object | None, name: str) -> int | None:
    if usage is None:
        return None
    value = getattr(usage, name, None)
    return int(value) if value is not None else None


def _result_from_response(
    response: object,
    *,
    fallback_model: str,
    preserve_newlines: bool,
) -> AIResult:
    text = _normalize_text(
        str(getattr(response, "output_text", "") or ""),
        preserve_newlines=preserve_newlines,
    )
    usage = getattr(response, "usage", None)
    return AIResult(
        text=text,
        model=str(getattr(response, "model", None) or fallback_model),
        request_id=getattr(response, "_request_id", None),
        input_tokens=_usage_value(usage, "input_tokens"),
        output_tokens=_usage_value(usage, "output_tokens"),
        total_tokens=_usage_value(usage, "total_tokens"),
    )


def _error_category(exc: Exception) -> str:
    if openai is None:
        return "sdk_unavailable"

    error_categories = (
        ("authentication", getattr(openai, "AuthenticationError", None)),
        ("permission", getattr(openai, "PermissionDeniedError", None)),
        ("rate_limit", getattr(openai, "RateLimitError", None)),
        ("timeout", getattr(openai, "APITimeoutError", None)),
        ("connection", getattr(openai, "APIConnectionError", None)),
        ("not_found", getattr(openai, "NotFoundError", None)),
        ("bad_request", getattr(openai, "BadRequestError", None)),
        ("api_status", getattr(openai, "APIStatusError", None)),
    )
    for category, error_type in error_categories:
        if error_type is not None and isinstance(exc, error_type):
            return category
    return "unexpected"


def _log_failure(exc: Exception, *, purpose: str, model: str | None) -> None:
    """Log operational metadata without logging prompts, responses, or secrets."""

    logger.warning(
        "openai_request_failed purpose=%s category=%s exception=%s model=%s request_id=%s status=%s",
        purpose,
        _error_category(exc),
        type(exc).__name__,
        model,
        getattr(exc, "request_id", None),
        getattr(exc, "status_code", None),
    )


def _log_success(result: AIResult, *, purpose: str) -> None:
    logger.info(
        "openai_request_succeeded purpose=%s model=%s request_id=%s input_tokens=%s "
        "output_tokens=%s total_tokens=%s",
        purpose,
        result.model,
        result.request_id,
        result.input_tokens,
        result.output_tokens,
        result.total_tokens,
    )


def _response_request(
    *,
    config: AIConfig,
    prompt: str,
    instructions: str | None,
) -> dict[str, object]:
    """Build a Responses request without changing legacy calls that omit instructions."""

    request: dict[str, object] = {
        "model": config.model,
        "input": prompt,
        "store": config.store_responses,
    }
    if instructions is not None and instructions.strip():
        request["instructions"] = instructions.strip()
    return request


def generate_result(
    prompt: str,
    *,
    config: AIConfig | None = None,
    preserve_newlines: bool = False,
    purpose: str = "text",
    instructions: str | None = None,
) -> AIResult | None:
    """Generate text synchronously and return safe response metadata on success."""

    if not prompt.strip():
        return None

    client = _get_sync_openai_client()
    if client is None:
        return None

    config = config or AIConfig.from_env()
    try:
        response = client.with_options(
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        ).responses.create(
            **_response_request(config=config, prompt=prompt, instructions=instructions)
        )
        result = _result_from_response(
            response,
            fallback_model=config.model,
            preserve_newlines=preserve_newlines,
        )
        if not result.text:
            return None
        _log_success(result, purpose=purpose)
        return result
    except Exception as exc:
        _log_failure(exc, purpose=purpose, model=config.model)
        return None


async def generate_result_async(
    prompt: str,
    *,
    config: AIConfig | None = None,
    preserve_newlines: bool = False,
    purpose: str = "text",
    instructions: str | None = None,
) -> AIResult | None:
    """Generate text with the native asynchronous OpenAI client."""

    if not prompt.strip():
        return None

    client = _get_async_openai_client()
    if client is None:
        return None

    config = config or AIConfig.from_env()
    try:
        response = await client.with_options(
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        ).responses.create(
            **_response_request(config=config, prompt=prompt, instructions=instructions)
        )
        result = _result_from_response(
            response,
            fallback_model=config.model,
            preserve_newlines=preserve_newlines,
        )
        if not result.text:
            return None
        _log_success(result, purpose=purpose)
        return result
    except Exception as exc:
        _log_failure(exc, purpose=purpose, model=config.model)
        return None


async def generate_private_result_async(
    prompt: str,
    *,
    workload: str,
    purpose: str,
    policy: AIPlatformPolicy | None = None,
    preserve_newlines: bool = False,
    require_enhanced_retention: bool = True,
    instructions: str | None = None,
) -> AIResult | None:
    """Run an async private-content request through the fail-closed privacy policy."""

    config = private_ai_config(
        workload=workload,
        policy=policy,
        require_enhanced_retention=require_enhanced_retention,
    )
    return await generate_result_async(
        prompt,
        config=config,
        preserve_newlines=preserve_newlines,
        purpose=purpose,
        instructions=instructions,
    )


def generate_text(
    prompt: str,
    *,
    config: AIConfig | None = None,
    preserve_newlines: bool = False,
    purpose: str = "text",
) -> str:
    """Generate text synchronously, returning an empty string on failure."""

    result = generate_result(
        prompt,
        config=config,
        preserve_newlines=preserve_newlines,
        purpose=purpose,
    )
    return result.text if result else ""


def generate_markdown(
    prompt: str,
    *,
    config: AIConfig | None = None,
    purpose: str = "markdown",
) -> str:
    """Generate Discord markdown while preserving line breaks."""

    return generate_text(
        prompt,
        config=config,
        preserve_newlines=True,
        purpose=purpose,
    )


async def generate_text_async(
    prompt: str,
    *,
    config: AIConfig | None = None,
    purpose: str = "text",
) -> str:
    """Generate text without blocking Discord's event loop."""

    result = await generate_result_async(prompt, config=config, purpose=purpose)
    return result.text if result else ""


async def generate_markdown_async(
    prompt: str,
    *,
    config: AIConfig | None = None,
    purpose: str = "markdown",
) -> str:
    """Generate Discord markdown without blocking Discord's event loop."""

    result = await generate_result_async(
        prompt,
        config=config,
        preserve_newlines=True,
        purpose=purpose,
    )
    return result.text if result else ""
