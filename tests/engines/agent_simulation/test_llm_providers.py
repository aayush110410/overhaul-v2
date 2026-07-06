"""
Tests for LLM Provider abstraction.

Verifies:
1. FallbackProvider returns heuristic JSON responses
2. OpenAIProvider falls back gracefully when no API key
3. OllamaProvider falls back gracefully when server unavailable
4. auto_provider detects best available provider
"""

import pytest
import json
from engines.agent_simulation.llm_providers import (
    FallbackProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    auto_provider,
)


class TestFallbackProvider:
    def test_returns_valid_json(self):
        p = FallbackProvider()
        result = p.complete("What should office workers do?")
        # Should be valid JSON
        parsed = json.loads(result)
        assert "preferred_routes" in parsed
        assert "avoid_zones" in parsed
        assert "segment_mood" in parsed
        assert "confidence" in parsed

    def test_includes_dissenting_signals(self):
        p = FallbackProvider()
        result = p.complete("avoid the highway")
        parsed = json.loads(result)
        assert isinstance(parsed.get("avoid_zones"), list)

    def test_confidence_in_range(self):
        p = FallbackProvider()
        for prompt in ["congestion", "avoid", "frustrated", "normal"]:
            result = p.complete(prompt)
            parsed = json.loads(result)
            assert 0.0 <= parsed["confidence"] <= 1.0


class TestOpenAIProvider:
    def test_falls_back_when_no_api_key(self):
        p = OpenAIProvider(api_key="")
        result = p.complete("Test prompt")
        parsed = json.loads(result)
        assert "preferred_routes" in parsed
        assert "confidence" in parsed

    def test_falls_back_when_invalid_key(self):
        p = OpenAIProvider(api_key="invalid-key-12345")
        result = p.complete("What are preferred routes?")
        # Should fall back to heuristic (API call fails)
        parsed = json.loads(result)
        assert "preferred_routes" in parsed


class TestAnthropicProvider:
    def test_falls_back_when_no_api_key(self):
        p = AnthropicProvider(api_key="")
        result = p.complete("Test prompt")
        parsed = json.loads(result)
        assert "preferred_routes" in parsed
        assert "confidence" in parsed

    def test_falls_back_when_invalid_key(self):
        p = AnthropicProvider(api_key="sk-ant-invalid")
        result = p.complete("What are preferred routes?")
        parsed = json.loads(result)
        assert "preferred_routes" in parsed


class TestOllamaProvider:
    def test_falls_back_when_server_unavailable(self):
        p = OllamaProvider(base_url="http://localhost:9999")
        result = p.complete("What are preferred routes?")
        parsed = json.loads(result)
        assert "preferred_routes" in parsed
        assert "confidence" in parsed


class TestAutoProvider:
    def test_returns_fallback_when_no_keys(self):
        import os
        # Ensure no API keys are set
        original = os.environ.get("OPENAI_API_KEY")
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        try:
            p = auto_provider()
            result = p.complete("Test prompt")
            parsed = json.loads(result)
            assert "preferred_routes" in parsed
        finally:
            if original is not None:
                os.environ["OPENAI_API_KEY"] = original
