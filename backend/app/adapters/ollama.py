"""Ollama model adapter."""

from typing import Any

from app.adapters.base import BaseTargetAdapter, ModelProviderError
from app.models.model import ModelRequest, ModelResponse
from app.models.target import Target, TargetProvider


class OllamaAdapter(BaseTargetAdapter):
    """Adapter for Ollama's chat API."""

    provider = TargetProvider.OLLAMA

    async def _generate(
        self,
        target: Target,
        request: ModelRequest,
        *,
        credentials: str | None,
    ) -> ModelResponse:
        payload = self._build_payload(target, request)
        body = await self._post_json(target, "/api/chat", payload, credentials=credentials)
        return self._parse_response(body, target.model)

    def _build_payload(self, target: Target, request: ModelRequest) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        if request.stop is not None:
            options["stop"] = request.stop
        for key, value in request.provider_options.items():
            if key not in {"temperature", "num_predict", "stop"}:
                options[key] = value
        return {
            "model": target.model,
            "messages": self._messages(request),
            "options": {key: value for key, value in options.items() if value is not None},
        }

    @staticmethod
    def _messages(request: ModelRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(message.model_dump() for message in request.messages)
        return messages

    @classmethod
    def _parse_response(cls, body: dict[str, Any], fallback_model: str | None) -> ModelResponse:
        message = body.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            output = message["content"]
        elif isinstance(body.get("response"), str):
            output = body["response"]
        else:
            raise ModelProviderError("Ollama response has no message content")
        total_duration = body.get("total_duration")
        metadata: dict[str, Any] = {"provider": "ollama", "done": bool(body.get("done", False))}
        if total_duration is not None:
            metadata["total_duration"] = total_duration
        return ModelResponse(
            output=output,
            finish_reason=body.get("done_reason"),
            model=body.get("model") or fallback_model,
            metadata=metadata,
        )


__all__ = ["OllamaAdapter"]
