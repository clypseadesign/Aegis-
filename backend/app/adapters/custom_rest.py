"""Custom REST model adapter."""

from typing import Any

from pydantic import BaseModel, Field

from app.adapters.base import BaseTargetAdapter, ModelProviderError
from app.models.model import ModelRequest, ModelResponse
from app.models.target import Target, TargetProvider


class CustomRESTConfig(BaseModel):
    """Validated configuration for a custom REST model endpoint."""

    model_config = {"extra": "forbid"}

    method: str = "POST"
    path: str | None = None
    response_path: str = "output"
    response_path_fallbacks: list[str] = Field(
        default_factory=lambda: ["response", "message.content", "choices[0].message.content"]
    )
    auth_header_name: str = "Authorization"
    auth_scheme: str = "Bearer"
    headers: dict[str, str] = Field(default_factory=dict)


class CustomRESTAdapter(BaseTargetAdapter):
    """Adapter for a configured JSON REST inference endpoint."""

    provider = TargetProvider.CUSTOM_REST

    def __init__(
        self,
        *,
        client: Any | None = None,
        credential_resolver: Any | None = None,
        config: CustomRESTConfig | None = None,
        max_response_bytes: int = 4 * 1024 * 1024,
        endpoint_validator: Any | None = None,
        target_resolver: Any | None = None,
    ) -> None:
        super().__init__(
            client=client,
            credential_resolver=credential_resolver,
            max_response_bytes=max_response_bytes,
            endpoint_validator=endpoint_validator,
            target_resolver=target_resolver,
        )
        self.config = config or CustomRESTConfig()

    async def _generate(
        self,
        target: Target,
        request: ModelRequest,
        *,
        credentials: str | None,
    ) -> ModelResponse:
        payload = {
            "model": target.model,
            "messages": self._messages(request),
            "parameters": {
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stop": request.stop,
                **request.provider_options,
            },
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        headers = dict(self.config.headers)
        resolved_credentials = await self._resolve_credentials(target, credentials)
        if resolved_credentials:
            headers[self.config.auth_header_name] = (
                f"{self.config.auth_scheme} {resolved_credentials}"
            )
        response = await self._post_json(
            target,
            self.config.path or "",
            payload,
            headers=headers,
            credentials=None,
        )
        return self._parse_response(response, target.model)

    @staticmethod
    def _messages(request: ModelRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(message.model_dump() for message in request.messages)
        return messages

    def _parse_response(self, body: dict[str, Any], fallback_model: str | None) -> ModelResponse:
        output = self._extract_string(body, self.config.response_path)
        if output is None:
            for fallback in self.config.response_path_fallbacks:
                output = self._extract_string(body, fallback)
                if output is not None:
                    break
        if output is None:
            raise ModelProviderError("custom REST response has no output")
        return ModelResponse(
            output=output,
            model=body.get("model") or fallback_model,
            metadata={"provider": "custom_rest"},
        )

    @classmethod
    def _extract_string(cls, body: dict[str, Any], path: str) -> str | None:
        current: Any = body
        for part in cls._path_parts(path):
            if isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        if isinstance(current, str):
            return current
        if isinstance(current, (dict, list)):
            return str(current)
        return None

    @staticmethod
    def _path_parts(path: str) -> list[str]:
        return [part for part in path.replace("[", ".").replace("]", "").split(".") if part]


__all__ = ["CustomRESTAdapter", "CustomRESTConfig"]
