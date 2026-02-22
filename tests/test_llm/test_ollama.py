"""Tests for the Ollama LLM backend."""

import pytest
import httpx

from autogen.llm.ollama import OllamaBackend


@pytest.mark.asyncio
async def test_generate_parses_response(httpx_mock) -> None:
    """OllamaBackend.generate() correctly parses the API response."""
    httpx_mock.add_response(
        url="http://test-ollama:11434/api/chat",
        json={
            "model": "test-model",
            "message": {
                "role": "assistant",
                "content": "```yaml\nalias: Test Automation\n```",
            },
            "done": True,
            "prompt_eval_count": 100,
            "eval_count": 50,
        },
    )

    backend = OllamaBackend(base_url="http://test-ollama:11434", model="test-model")
    response = await backend.generate("system prompt", "user prompt")
    await backend.close()

    assert "alias: Test Automation" in response.content
    assert response.model == "test-model"
    assert response.prompt_tokens == 100
    assert response.completion_tokens == 50


@pytest.mark.asyncio
async def test_health_check_success(httpx_mock) -> None:
    """health_check returns True when Ollama is reachable."""
    httpx_mock.add_response(
        url="http://test-ollama:11434/",
        text="Ollama is running",
    )

    backend = OllamaBackend(base_url="http://test-ollama:11434", model="test-model")
    result = await backend.health_check()
    await backend.close()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(httpx_mock) -> None:
    """health_check returns False when Ollama is unreachable."""
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

    backend = OllamaBackend(base_url="http://test-ollama:11434", model="test-model")
    result = await backend.health_check()
    await backend.close()

    assert result is False
