from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from app.config import get_settings

try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover
    Groq = None  # type: ignore


class LLMError(RuntimeError):
    pass


def chat_json(*, schema: Dict[str, Any], system: str, user: str, temperature: float | None = None) -> Dict[str, Any]:
    """Strict Groq client — uses exactly the model specified in GROQ_MODEL (or DEFAULT if unset).
    No aliasing, no multi-candidate fallbacks, no guessing.
    """
    global LAST_USED_MODEL, LAST_OVERRIDE_NOTE

    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set; cannot perform LLM call.")
    if not settings.GROQ_MODEL:
        raise LLMError("GROQ_MODEL is not set; cannot perform LLM call.")
    if Groq is None:
        raise LLMError("groq SDK not available.")

    client = Groq(api_key=settings.GROQ_API_KEY)
    temp = settings.GROQ_TEMPERATURE if temperature is None else temperature
    requested_model = settings.GROQ_MODEL.strip()

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "strict_schema",
            "schema": schema,
            "strict": True,
        },
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    # Simple retry for transient errors (e.g., intermittent 5xx)
    last_error: Optional[str] = None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=requested_model,
                messages=messages,
                temperature=temp,
                response_format=response_format,
            )
            content = resp.choices[0].message.content
            if not content:
                raise LLMError("Empty response content from LLM.")
            return json.loads(content)
        except Exception as e:  # noqa: PERF203
            last_error = str(e)
            if attempt == 0:
                time.sleep(0.5)
                continue
            # Give the exact underlying reason back to the caller (nodes/UI will display it)
            raise LLMError(f"LLM call failed (model='{requested_model}'): {last_error}")
    return {}
