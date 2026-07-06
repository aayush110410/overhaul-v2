"""
LLM Provider Abstraction for SegmentBrain Distillation
=====================================================

Supports three backends:
  - OpenAI GPT models (api_key required)
  - Anthropic Claude models (api_key required)
  - Ollama local models (no key required, localhost)

Falls back to heuristic response when LLM is unavailable.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional
import httpx


class LLMProvider:
    """Abstract interface for LLM providers used in SegmentBrain distillation."""

    def complete(self, prompt: str, **kwargs) -> str:
        """Return LLM response text for the given prompt."""
        raise NotImplementedError


class FallbackProvider(LLMProvider):
    """Heuristic fallback when no LLM is configured."""

    def complete(self, prompt: str, **kwargs) -> str:
        """Return a heuristic response based on prompt content."""
        prompt_lower = prompt.lower()
        if "avoid" in prompt_lower:
            return json.dumps({
                "preferred_routes": [],
                "avoid_zones": ["high_congestion_corridor"],
                "segment_mood": "frustrated",
                "confidence": 0.4,
                "dissenting_signals": ["alternative_path_blocked"],
            })
        elif "congestion" in prompt_lower:
            return json.dumps({
                "preferred_routes": ["metro_alternative"],
                "avoid_zones": ["arterial_road"],
                "segment_mood": "adaptive",
                "confidence": 0.5,
                "dissenting_signals": [],
            })
        elif "frustrated" in prompt_lower:
            return json.dumps({
                "preferred_routes": ["reroute_suggested"],
                "avoid_zones": [],
                "segment_mood": "frustrated",
                "confidence": 0.3,
                "dissenting_signals": ["no_good_options"],
            })
        else:
            return json.dumps({
                "preferred_routes": ["current_route"],
                "avoid_zones": [],
                "segment_mood": "stable",
                "confidence": 0.5,
                "dissenting_signals": [],
            })


class OpenAIProvider(LLMProvider):
    """OpenAI GPT models via REST API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self._fallback = FallbackProvider()

    def complete(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            return self._fallback.complete(prompt)

        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", 0.3),
            }
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            return self._fallback.complete(prompt)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude models via REST API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-haiku-20251107"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self._fallback = FallbackProvider()

    def complete(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            return self._fallback.complete(prompt)

        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": kwargs.get("max_tokens", 512),
            }
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["content"][0]["text"]
        except Exception:
            return self._fallback.complete(prompt)


class OllamaProvider(LLMProvider):
    """Local Ollama server — no API key required."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._fallback = FallbackProvider()

    def complete(self, prompt: str, **kwargs) -> str:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": kwargs.get("temperature", 0.3)},
                    },
                )
                resp.raise_for_status()
                return resp.json()["response"]
        except Exception:
            return self._fallback.complete(prompt)


def auto_provider() -> LLMProvider:
    """
    Auto-detect the best available LLM provider.

    Priority: OpenAI > Anthropic > Ollama > Fallback
    """
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIProvider()
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    return OllamaProvider()  # Will fall back to heuristic on connection error


def build_segmentbrain_provider(
    llm: Optional[LLMProvider] = None,
) -> Callable[[List[dict]], CollectiveTruth]:
    """
    Wrap an LLMProvider into a SegmentBrain-compatible callable.

    The wrapper:
    1. Builds a distillation prompt from discovery dicts
    2. Calls the LLM to get a JSON response
    3. Parses the JSON into a CollectiveTruth dataclass

    Args:
        llm: LLMProvider instance. Uses auto_provider() if None.

    Returns:
        A callable that takes List[dict] and returns CollectiveTruth.
    """
    from engines.agent_simulation.brains.collective_truth import CollectiveTruth

    if llm is None:
        llm = auto_provider()

    def provider(discoveries: List[dict]) -> CollectiveTruth:
        prompt = _build_distillation_prompt(discoveries)
        response = llm.complete(prompt)

        try:
            parsed = json.loads(response)
            return CollectiveTruth(
                timestep=0,
                preferred_routes=parsed.get("preferred_routes", []),
                avoid_zones=parsed.get("avoid_zones", []),
                segment_mood=parsed.get("segment_mood", "stable"),
                confidence=parsed.get("confidence", 0.5),
                dissenting_signals=parsed.get("dissenting_signals", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return CollectiveTruth(
                timestep=0,
                preferred_routes=["maintain_current_route"],
                avoid_zones=[],
                segment_mood="stable",
                confidence=0.3,
                dissenting_signals=["LLM response parsing failed"],
                stale=True,
            )

    return provider


def _build_distillation_prompt(discoveries: List[dict]) -> str:
    """Build a distillation prompt from discovery dicts."""
    if not discoveries:
        return "No recent observations. Synthesize a stable state."

    lines = []
    for d in discoveries:
        data = d.get("discovery_data", {})
        lines.append(
            f"- Sentinel {d.get('sentinel_id', '?')}: "
            f"{data.get('observation', 'N/A')} "
            f"(route: {data.get('route', '?')}, "
            f"speed: {data.get('speed_kmh', '?')} km/h)"
        )
    discoveries_text = "\n".join(lines) if lines else "No observations."

    return f"""You are the collective intelligence coordinator for a Delhi NCR traffic segment.

Recent sentinel observations:
{discoveries_text}

Synthesize the collective truth. Respond with ONLY valid JSON:
{{"preferred_routes": [...], "avoid_zones": [...], "segment_mood": "frustrated|adaptive|stable|optimistic", "confidence": 0.0-1.0, "dissenting_signals": [...]}}"""

