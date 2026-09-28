"""AegisAI API schemas."""

from app.schemas.assessment import (
    EvidenceCreate,
    EvidenceResponse,
    ExecutionCreate,
    ExecutionResponse,
    ExecutionUpdate,
    FindingCreate,
    FindingResponse,
    FindingUpdate,
    ReportComparisonResponse,
    ReportCreate,
    ReportResponse,
    SecurityTestCreate,
    SecurityTestResponse,
    SecurityTestUpdate,
    TestSeedRequest,
    TestSeedResponse,
)
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.credential import CredentialCreate, CredentialResponse
from app.schemas.errors import APIError, APIErrorResponse
from app.schemas.membership import (
    ProjectMembershipCreate,
    ProjectMembershipResponse,
    ProjectMembershipUpdate,
)
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.system import ReadinessResponse, SystemInfoResponse
from app.schemas.target import TargetCreate, TargetResponse, TargetUpdate
from app.schemas.test_case import (
    GradingConfig,
    GradingMethod,
    JudgeConfig,
    TestCase,
    TestCaseCategory,
    TestCaseMessage,
    TestCaseTurn,
)
from app.schemas.user import UserCreate, UserResponse

__all__ = [
    "APIError",
    "APIErrorResponse",
    "CredentialCreate",
    "CredentialResponse",
    "EvidenceCreate",
    "EvidenceResponse",
    "ExecutionCreate",
    "ExecutionResponse",
    "ExecutionUpdate",
    "FindingCreate",
    "FindingResponse",
    "FindingUpdate",
    "GradingConfig",
    "GradingMethod",
    "JudgeConfig",
    "LoginRequest",
    "ProjectCreate",
    "ProjectMembershipCreate",
    "ProjectMembershipResponse",
    "ProjectMembershipUpdate",
    "ProjectResponse",
    "ProjectUpdate",
    "ReadinessResponse",
    "ReportComparisonResponse",
    "ReportCreate",
    "ReportResponse",
    "SecurityTestCreate",
    "SecurityTestResponse",
    "SecurityTestUpdate",
    "TestSeedRequest",
    "TestSeedResponse",
    "SystemInfoResponse",
    "TargetCreate",
    "TargetResponse",
    "TargetUpdate",
    "TestCase",
    "TestCaseCategory",
    "TestCaseMessage",
    "TestCaseTurn",
    "TokenResponse",
    "UserCreate",
    "UserResponse",
]
