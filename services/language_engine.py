from __future__ import annotations
import asyncio
from typing import Any, Dict, Literal, Optional
from openai import AsyncOpenAI

Place = Literal["embed", "chat"]
Intent = Literal[
    "roll-line", "8ball-line", "misfortune-cookie",
    "cta-share", "morning-broadcast-bit", "generic"
]

class LanguageEngine:
    def __init__(self, model: str, timeout_s: float = 6.0):
        self.client = AsyncOpenAI()
        self.model = model
        self.timeout_s = timeout_s

    def _system_prompt(self, place: Place) -> str:
        return (
            "You are Wilhelmina, a cyber-occult witch DJ. "
            "Voice: haunted glitch, sharp and theatrical, PG-13, concise. "
            "If output is for an embed, keep to 1–2 sentences."
        )

    def _user_prompt(self, intent: Intent, variables: Dict[str, Any]) -> str:
        if intent == "roll-line":
            return (
                "Write one punchy line reacting to a dice roll.\n"
                f"Dice: d{variables['sides']}. Result: {variables['result']}."
                " Avoid numbers beyond the given result; be playful ominous."
            )
        if intent == "8ball-line":
            return (
                "Write a classic Magic 8-Ball style answer in Wilhelmina's voice.\n"
                f"Verdict: {variables['verdict']} (Affirmative/Vague/Negative). "
                f"Question: {variables.get('question','')}\n"
                "Keep it to one short sentence."
            )
        if intent == "misfortune-cookie":
            return (
                "Write a cryptic fortune as if cracked from a cursed cookie. "
                "No categories; just one eerie line. Keep to one sentence."
            )
        if intent == "cta-share":
            return "Write one-sentence CTA to share the server when voice is lively."
        if intent == "morning-broadcast-bit":
            return "Write a short omen or sting for the morning broadcast."
        return variables.get("prompt", "Say one short on-brand line.")

    async def compose(
        self,
        *,
        place: Place,
        intent: Intent,
        variables: Dict[str, Any],
        fallback: Optional[str] = None,
        temperature: float = 0.9,
        max_tokens: int = 80,
    ) -> str:
        try:
            resp = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._system_prompt(place)},
                        {"role": "user", "content": self._user_prompt(intent, variables)},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self.timeout_s,
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or (fallback or "The static withholds its secrets.")
        except Exception:
            return fallback or "The signal stutters—try again soon."

_engine_singleton: Optional[LanguageEngine] = None

def get_engine(model_env: Optional[str] = None) -> LanguageEngine:
    import os
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = LanguageEngine(model=os.getenv("MODEL_WILHELMINA_MAIN", model_env or "gpt-4o-mini"))
    return _engine_singleton
