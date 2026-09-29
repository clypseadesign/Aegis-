"""Assessment domain schemas for AegisAI."""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.execution import ExecutionResult, ExecutionStatus
from app.models.finding import FindingSeverity, FindingStatus
from app.schemas.test_case import TestCaseCategory


class SeedReportLike(Protocol):
    """Structural type for the result of a seeding run."""

    created: list[str]
    skipped: list[str]
    invalid: dict[str, str]


class SecurityTestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    provider: str = Field(min_length=1, max_length=100)
    required_capabilities: list[str] = Field(default_factory=list, max_length=50)
    config: dict[str, Any] = Field(default_factory=dict)


class SecurityTestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    required_capabilities: list[str] | None = Field(default=None, max_length=50)
    config: dict[str, Any] | None = None


class SecurityTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    provider: str
    required_capabilities: list[str]
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: UUID | None = None
    target_id: UUID | None = None


class ExecutionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ExecutionStatus | None = None
    result: ExecutionResult | None = None


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    test_id: UUID | None
    target_id: UUID | None
    status: ExecutionStatus
    result: ExecutionResult
    started_at: datetime | None
    completed_at: datetime | None
    # Why the execution failed, when it did. Without this the UI could only
    # report "failed", which is indistinguishable between a misconfigured
    # target, a bad credential, and a provider outage.
    error: str | None = None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class FindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    execution_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    severity: FindingSeverity = FindingSeverity.MEDIUM
    details: dict[str, Any] = Field(default_factory=dict)


class FindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FindingStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class FindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    execution_id: UUID
    title: str
    description: str | None
    severity: FindingSeverity
    status: FindingStatus
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    finding_id: UUID
    kind: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    content: dict[str, Any] = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    finding_id: UUID
    kind: str
    description: str | None
    content: dict[str, Any]
    created_at: datetime


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    format: str = Field(default="json", min_length=1, max_length=20)


class TestSeedRequest(BaseModel):
    """Request schema for loading the bundled security test library."""

    model_config = ConfigDict(extra="forbid")

    category: list[TestCaseCategory] = Field(
        default_factory=list,
        description="Restrict seeding to these categories. Empty means all.",
    )


class TestSeedResponse(BaseModel):
    """Response schema describing the outcome of a library seed."""

    model_config = ConfigDict(extra="forbid")

    created: int
    skipped: int
    invalid: int
    total: int

    @classmethod
    def from_report(cls, report: "SeedReportLike") -> "TestSeedResponse":
        """Build a response from a seed report.

        Takes a structural type so the schema layer does not import the
        service layer.
        """

        created = len(report.created)
        skipped = len(report.skipped)
        invalid = len(report.invalid)
        return cls(
            created=created,
            skipped=skipped,
            invalid=invalid,
            total=created + skipped + invalid,
        )


class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    format: str
    path: str
    version: int = 1
    generated_at: datetime | None = None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ReportComparisonResponse(BaseModel):
    """Result of comparing two report runs."""

    model_config = ConfigDict(extra="forbid")

    report_a_id: UUID
    report_b_id: UUID
    new_count: int = 0
    resolved_count: int = 0
    regressed_count: int = 0
    improved_count: int = 0
    unchanged_count: int = 0
    new_findings: list[dict[str, Any]] = Field(default_factory=list)
    resolved_findings: list[dict[str, Any]] = Field(default_factory=list)
    regressed_findings: list[dict[str, Any]] = Field(default_factory=list)
    improved_findings: list[dict[str, Any]] = Field(default_factory=list)
    unchanged_findings: list[dict[str, Any]] = Field(default_factory=list)
