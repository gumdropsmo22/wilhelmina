from __future__ import annotations
"""
Unify OpenAI calls behind this module.
# STUB: Wire actual client in C10 with error handling & retries.
"""
from typing import Any, Dict

class AIClient:
    def __init__(self, api_key: str | None):
        self.api_key = api_key
        # STUB: init real SDK client here

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        # STUB: perform real call
        return {"role": "assistant", "content": "STUB: not yet implemented"}
