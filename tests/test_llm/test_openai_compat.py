"""Tests for the OpenAI-compatible LLM backend."""

import pytest
import httpx

from autogen.llm.openai_compat import OpenAICompatBackend


@pytest.mark.asyncio
async def test_generate_parses_response(httpx_mock) -> None:
    """OpenAICompatBackend.generate() correctly parses the chat completions response."""
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={
            "id": "chatcmpl-abc123",
            "object": "chat.completion",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "```yaml\nalias: Test Automation\ntrigger:\n  - platform: state\n```",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 150,
                "completion_tokens": 40,
                "total_tokens": 190,
            },
        },
    )

    backend = OpenAICompatBackend(
        base_url="https://api.openai.com",
        model="gpt-4o",
        api_key="sk-test-key",
    )
    response = await backend.generate("system prompt", "user prompt")
    await backend.close()

    assert "alias: Test Automation" in response.content
    assert response.model == "gpt-4o"
    assert response.prompt_tokens == 150
    assert response.completion_tokens == 40


@pytest.mark.asyncio
async def test_auth_header_is_set(httpx_mock) -> None:
    """API key is sent as a Bearer token in the Authorization header."""
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "test"}, "finish_reason": "stop"}],
            "usage": {},
        },
    )

    backend = OpenAICompatBackend(
        base_url="https://api.openai.com",
        model="gpt-4o",
        api_key="sk-test-key-123",
    )
    await backend.generate("sys", "usr")
    await backend.close()

    request = httpx_mock.get_request()
    assert request.headers["authorization"] == "Bearer sk-test-key-123"


@pytest.mark.asyncio
async def test_health_check_success(httpx_mock) -> None:
    """health_check returns True when the API is reachable."""
    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        json={"data": [{"id": "gpt-4o"}]},
    )

    backend = OpenAICompatBackend(
        base_url="https://api.openai.com",
        model="gpt-4o",
        api_key="sk-test",
    )
    result = await backend.health_check()
    await backend.close()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(httpx_mock) -> None:
    """health_check returns False when the API is unreachable."""
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

    backend = OpenAICompatBackend(
        base_url="https://api.openai.com",
        model="gpt-4o",
        api_key="sk-test",
    )
    result = await backend.health_check()
    await backend.close()

    assert result is False
