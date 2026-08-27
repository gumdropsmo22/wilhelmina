from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from services import ai

logger = logging.getLogger("wilhelmina.memory.extractor")


@dataclass(frozen=True)
class ProviderResult:
    payload: dict[str, Any]
    model: str
    request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


def _usage_value(usage: object | None, name: str) -> int | None:
    if usage is None:
        return None
    value = getattr(usage, name, None)
    return int(value) if value is not None else None


def provider_ready(*, policy: ai.AIPlatformPolicy | None = None) -> bool:
    if not ai.ai_available():
        return False
    try:
        ai.private_ai_config(workload="memory", policy=policy)
    except (ai.AIPrivacyConfigurationError, ValueError):
        return False
    return True


async def extract_structured(
    *,
    instructions: str,
    input_text: str,
    schema_name: str,
    schema: Mapping[str, Any],
    policy: ai.AIPlatformPolicy | None = None,
) -> ProviderResult | None:
    """Run strict Responses API JSON-schema extraction with private retention settings."""

    config = ai.private_ai_config(workload="memory", policy=policy)
    client = ai._get_async_openai_client()  # shared provider client; intentionally reused here
    if client is None:
        return None
    try:
        response = await client.with_options(
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        ).responses.create(
            model=config.model,
            instructions=instructions,
            input=[
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_text}],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": dict(schema),
                    "strict": True,
                }
            },
            store=False,
        )
        raw = str(getattr(response, "output_text", "") or "").strip()
        if not raw:
            logger.warning("memory_extractor_empty_output model=%s", config.model)
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            logger.warning("memory_extractor_invalid_root model=%s", config.model)
            return None
        usage = getattr(response, "usage", None)
        result = ProviderResult(
            payload=payload,
            model=str(getattr(response, "model", None) or config.model),
            request_id=getattr(response, "_request_id", None),
            input_tokens=_usage_value(usage, "input_tokens"),
            output_tokens=_usage_value(usage, "output_tokens"),
            total_tokens=_usage_value(usage, "total_tokens"),
        )
        logger.info(
            "memory_extractor_succeeded model=%s request_id=%s input_tokens=%s "
            "output_tokens=%s total_tokens=%s",
            result.model,
            result.request_id,
            result.input_tokens,
            result.output_tokens,
            result.total_tokens,
        )
        return result
    except ai.AIPrivacyConfigurationError:
        raise
    except Exception as exc:
        logger.warning(
            "memory_extractor_failed model=%s exception=%s request_id=%s status=%s",
            config.model,
            type(exc).__name__,
            getattr(exc, "request_id", None),
            getattr(exc, "status_code", None),
        )
        return None
