"""Provider leaf-calls for the Reasoning Gateway.

Thin async wrappers over the REAL 4-model brain in ``llm/chat.py``. This is the
ONLY module in ``reasoning/`` that imports the concrete LLM transport — every
other module routes through the gateway (PATH.md invariant #5).

Two underlying API accounts back the four models:
  - ``openrouter``  → qwen, kimi, gpt_oss   (share one OPENROUTER_API_KEY + RPM)
  - ``google``      → gemini                (separate GEMINI_API_KEY)

Rate-limiting is therefore enforced per *account*, not per model.
"""
from __future__ import annotations

from typing import Any, Dict

from llm.chat import llm_chat_json, llm_chat_text

# Canonical model names understood by llm/chat.py's ``prefer`` argument.
PROVIDERS = ("qwen", "kimi", "gpt_oss", "gemini")

# Which upstream API account each model bills against (the real RPM boundary).
ACCOUNT_OF: Dict[str, str] = {
    "qwen": "openrouter",
    "kimi": "openrouter",
    "gpt_oss": "openrouter",
    "gemini": "google",
}


async def call_json(
    model: str,
    *,
    prompt: str,
    system: str = "",
    max_output_tokens: int = 700,
) -> Dict[str, Any]:
    """Call one model and return parsed JSON.

    ``llm_chat_json`` already strips code-fences, handles placeholder/fallback
    responses, and parses JSON. On unrecoverable failure it returns a dict with
    an ``error`` key, which the gateway treats as a batch failure.
    """
    return await llm_chat_json(
        prompt=prompt,
        system=system,
        prefer=model,
        max_output_tokens=max_output_tokens,
    )


async def call_text(
    model: str,
    *,
    prompt: str,
    system: str = "",
    max_output_tokens: int = 900,
) -> str:
    """Call one model and return plain text (used for the report narrative)."""
    return await llm_chat_text(
        prompt=prompt,
        system=system,
        prefer=model,
        max_output_tokens=max_output_tokens,
    )
