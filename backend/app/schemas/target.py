"""Target API schemas for AegisAI."""

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.target import TargetProvider, TargetStatus


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
