"""Target API schemas for AegisAI."""

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.target import TargetProvider, TargetStatus

# Path segments that are request paths, never part of a base URL.
#
# The endpoint is a BASE URL: AegisAI appends the provider's own path, so a
# value that already contains one of these produces a doubled path and an
# opaque HTTP 404 at run time (for example
# https://api.openrouter.ai/api/v1/chat/completions/api/chat). This is the
# single most common configuration mistake, so it is rejected up front.
#
# All known request paths are rejected for every fixed-path provider, not just
# the selected one. A user who pasted a hosted OpenAI-compatible URL but chose
# "Ollama" is mismatched in both ways, and checking only the chosen provider's
# suffix would miss it.
#
# CUSTOM_REST is excluded because its path is configurable and defaults to
# none, so the full URL is legitimate there.
PROVIDER_REQUEST_PATHS: tuple[str, ...] = (
    "/chat/completions",
    "/api/chat",
)


def _validate_endpoint_is_base_url(endpoint: str, provider: TargetProvider) -> None:
    """Reject an endpoint that already contains a provider request path."""

    if provider == TargetProvider.CUSTOM_REST:
        return

    path = urlsplit(endpoint).path.rstrip("/").lower()
    for request_path in PROVIDER_REQUEST_PATHS:
        if path.endswith(request_path) or request_path in path:
            raise ValueError(
                "endpoint must be the base URL, not the full request path. "
                f"AegisAI appends the request path itself, so enter the URL up "
                f"to but not including '{request_path}' (for example "
                "https://api.example.com/v1)."
            )


class TargetCreate(BaseModel):
    """Request schema for creating a project target."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    provider: TargetProvider
    endpoint: str = Field(min_length=1, max_length=2048)
    model: str | None = Field(default=None, max_length=255)
    capabilities: list[str] = Field(default_factory=list, max_length=50)
    timeout_seconds: float = Field(default=30.0, gt=0, le=3600)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
    status: TargetStatus = TargetStatus.ACTIVE
    authorization_attestation: Literal[True] = Field(
        description=(
            "Confirms the caller is authorized to security-test this target "
            "(e.g. they own it, or have explicit permission from its owner). "
            "AegisAI is a security testing tool; running it against a system "
            "without authorization may be illegal. This must be explicitly "
            "set to true — AegisAI refuses to create a target otherwise."
        ),
    )

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        """Accept only ordinary HTTP or HTTPS target endpoints."""

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("endpoint must be an absolute http or https URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint must not contain credentials")
        return value

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, value: list[str]) -> list[str]:
        """Normalize capability names without allowing empty entries."""

        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("capabilities must not contain empty values")
        return normalized

    @model_validator(mode="after")
    def validate_provider_configuration(self) -> "TargetCreate":
        """Require a model identifier for model-backed providers."""

        if (
            self.provider in {TargetProvider.OPENAI_COMPATIBLE, TargetProvider.OLLAMA}
            and not self.model
        ):
            raise ValueError("model is required for openai_compatible and ollama targets")
        _validate_endpoint_is_base_url(self.endpoint, self.provider)
        return self


class TargetUpdate(BaseModel):
    """Request schema for updating a project target."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    provider: TargetProvider | None = None
    endpoint: str | None = Field(default=None, min_length=1, max_length=2048)
    model: str | None = Field(default=None, max_length=255)
    capabilities: list[str] | None = Field(default=None, max_length=50)
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=10000)
    status: TargetStatus | None = None

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str | None) -> str | None:
        """Accept only ordinary HTTP or HTTPS target endpoints."""

        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("endpoint must be an absolute http or https URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint must not contain credentials")
        return value

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, value: list[str] | None) -> list[str] | None:
        """Normalize capability names without allowing empty entries."""

        if value is None:
            return None
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("capabilities must not contain empty values")
        return normalized

    @model_validator(mode="after")
    def require_update_field(self) -> "TargetUpdate":
        """Reject empty update payloads."""

        if not self.model_fields_set:
            raise ValueError("at least one target field must be supplied")
        return self

    @model_validator(mode="after")
    def validate_endpoint_against_provider(self) -> "TargetUpdate":
        """Apply the base-URL rule when the provider is known.

        A partial update may supply only the endpoint or only the provider, so
        the check runs when the endpoint is present and the provider is either
        supplied now or unchanged. Without the provider the pairing cannot be
        determined, so the value is left to the create path or a later update.
        """

        if self.endpoint is None:
            return self
        if self.provider is not None:
            _validate_endpoint_is_base_url(self.endpoint, self.provider)
        return self


class TargetResponse(BaseModel):
    """Response schema for a target."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    provider: TargetProvider
    endpoint: str
    model: str | None
    capabilities: list[str]
    timeout_seconds: float
    rate_limit_per_minute: int
    status: TargetStatus
    authorization_attested_by: UUID | None
    authorization_attested_at: datetime | None
    created_at: datetime
    updated_at: datetime
