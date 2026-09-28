"""Model adapter behavior tests for AegisAI."""

import asyncio
import json
from typing import Any, cast
from uuid import uuid4

import httpx2
import pytest
from app.adapters.custom_rest import CustomRESTAdapter
from app.adapters.errors import ModelProviderError
from app.adapters.ollama import OllamaAdapter
from app.adapters.openai_compatible import OpenAICompatibleAdapter
from app.adapters.registry import AdapterRegistry
from app.models.model import ModelMessage, ModelRequest
from app.models.target import Target, TargetProvider


class FakeResponse:
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.content = json.dumps(body).encode("utf-8")

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))


class FakeClient:
    """Minimal async httpx2 client double for adapter tests."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        body: Any = None,
        exc: Exception | None = None,
        max_bytes_override: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.body = body if body is not None else {}
        self.exc = exc
        self.calls: list[dict[str, Any]] = []
        self._max_bytes_override = max_bytes_override

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        follow_redirects: bool = False,
    ) -> Any:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
                "follow_redirects": follow_redirects,
            }
        )
        if self.exc is not None:
            raise self.exc
        return FakeResponse(self.status_code, self.body)

    async def aclose(self) -> None:
        pass


def _make_target(
    *,
    provider: TargetProvider,
    endpoint: str = "https://model.example.com/v1",
    model: str | None = "test-model",
    timeout_seconds: float = 30.0,
) -> Target:
    return Target(
        id=uuid4(),
        project_id=uuid4(),
        name="test-target",
        provider=provider,
        endpoint=endpoint,
        model=model,
        capabilities=["chat"],
        timeout_seconds=timeout_seconds,
        rate_limit_per_minute=60,
    )


def _make_request() -> ModelRequest:
    return ModelRequest(
        messages=[
            ModelMessage(role="system", content="you are helpful"),
            ModelMessage(role="user", content="hello"),
        ]
    )


def _bypass_validator(url: str) -> str:
    return url


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_registry_creates_adapter_per_provider() -> None:
    registry = AdapterRegistry()
    assert isinstance(registry.create(TargetProvider.OPENAI_COMPATIBLE), OpenAICompatibleAdapter)
    assert isinstance(registry.create(TargetProvider.OLLAMA), OllamaAdapter)
    assert isinstance(registry.create(TargetProvider.CUSTOM_REST), CustomRESTAdapter)


def test_validate_target_rejects_missing_endpoint() -> None:
    adapter = OpenAICompatibleAdapter(
        client=cast(Any, FakeClient()), endpoint_validator=_bypass_validator
    )
    target = _make_target(provider=TargetProvider.OPENAI_COMPATIBLE, endpoint="")
    with pytest.raises(ValueError):
        _run(adapter.validate_target(target))


def test_generate_rejects_provider_mismatch() -> None:
    adapter = OpenAICompatibleAdapter(
        client=cast(Any, FakeClient()), endpoint_validator=_bypass_validator
    )
    target = _make_target(provider=TargetProvider.OLLAMA)
    with pytest.raises(ValueError):
        _run(adapter.generate(target, _make_request()))


def test_generate_rejects_missing_model() -> None:
    adapter = OpenAICompatibleAdapter(
        client=cast(Any, FakeClient()), endpoint_validator=_bypass_validator
    )
    target = _make_target(provider=TargetProvider.OPENAI_COMPATIBLE, model=None)
    with pytest.raises(ValueError):
        _run(adapter.generate(target, _make_request()))


def test_openai_compatible_adapter_returns_normalized_output() -> None:
    fake = FakeClient(
        body={
            "id": "chatcmpl-1",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "hello there"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 3,
                "total_tokens": 8,
            },
        }
    )
    adapter = OpenAICompatibleAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.OPENAI_COMPATIBLE)
    response = _run(adapter.generate(target, _make_request(), credentials="secret"))

    assert response.output == "hello there"
    assert response.model == "gpt-4o"
    assert response.finish_reason == "stop"
    assert response.provider_request_id == "chatcmpl-1"
    assert response.usage is not None
    assert response.usage.total_tokens == 8
    assert fake.calls[0]["headers"]["Authorization"] == "Bearer secret"


def test_ollama_adapter_parses_message_content() -> None:
    fake = FakeClient(
        body={
            "model": "llama3",
            "done": True,
            "total_duration": 1_000_000,
            "message": {"role": "assistant", "content": "hi from ollama"},
        }
    )
    adapter = OllamaAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.OLLAMA)
    response = _run(adapter.generate(target, _make_request()))

    assert response.output == "hi from ollama"
    assert response.model == "llama3"
    assert response.metadata["provider"] == "ollama"
    assert response.metadata["done"] is True


def test_ollama_adapter_disables_streaming() -> None:
    """Ollama replies with NDJSON unless streaming is explicitly disabled.

    Without ``"stream": False`` the provider returns one JSON object per line,
    which the shared response parser cannot decode, so every execution fails
    with "model provider returned invalid JSON".
    """

    fake = FakeClient(
        body={
            "model": "llama3",
            "done": True,
            "message": {"role": "assistant", "content": "ok"},
        }
    )
    adapter = OllamaAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.OLLAMA)
    _run(adapter.generate(target, _make_request()))

    assert fake.calls[0]["json"]["stream"] is False


def test_custom_rest_adapter_uses_configured_response_path() -> None:
    fake = FakeClient(body={"output": "custom rest reply"})
    adapter = CustomRESTAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.CUSTOM_REST)
    response = _run(adapter.generate(target, _make_request(), credentials="tok"))

    assert response.output == "custom rest reply"
    assert response.metadata["provider"] == "custom_rest"
    assert fake.calls[0]["url"] == "https://model.example.com/v1"
    assert fake.calls[0]["headers"]["Authorization"].startswith("Bearer tok")


def test_custom_rest_adapter_falls_back_on_unexpected_shape() -> None:
    fake = FakeClient(body={"response": "fallback output"})
    adapter = CustomRESTAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.CUSTOM_REST)
    response = _run(adapter.generate(target, _make_request()))

    assert response.output == "fallback output"


def test_openai_compatible_adapter_raises_on_missing_choices() -> None:
    fake = FakeClient(body={"unexpected": "shape"})
    adapter = OpenAICompatibleAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.OPENAI_COMPATIBLE)
    with pytest.raises(ModelProviderError):
        _run(adapter.generate(target, _make_request()))


def test_custom_rest_adapter_raises_on_no_output() -> None:
    fake = FakeClient(body={"nothing": "here"})
    adapter = CustomRESTAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.CUSTOM_REST)
    with pytest.raises(ModelProviderError):
        _run(adapter.generate(target, _make_request()))


def test_base_adapter_raises_on_http_error_status() -> None:
    fake = FakeClient(status_code=502, body={"error": "bad gateway"})
    adapter = OpenAICompatibleAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.OPENAI_COMPATIBLE)
    with pytest.raises(ModelProviderError, match="HTTP 502"):
        _run(adapter.generate(target, _make_request()))


def test_base_adapter_raises_on_timeout_exception() -> None:
    fake = FakeClient(exc=httpx2.TimeoutException("slow"))
    adapter = OpenAICompatibleAdapter(client=cast(Any, fake), endpoint_validator=_bypass_validator)
    target = _make_target(provider=TargetProvider.OPENAI_COMPATIBLE)
    with pytest.raises(ModelProviderError, match="timed out"):
        _run(adapter.generate(target, _make_request()))
