"""AegisAI FastAPI application entry point."""

from fastapi import FastAPI

from app.api.errors import (
    AssessmentNotFoundError,
    AuthenticationRequiredError,
    CredentialNotFoundError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    MembershipConflictError,
    PermissionDeniedError,
    ProjectNotFoundError,
    RateLimitExceededError,
    TargetNotFoundError,
    assessment_not_found_handler,
    authentication_required_handler,
    credential_not_found_handler,
    email_already_registered_handler,
    invalid_credentials_handler,
    membership_conflict_handler,
    permission_denied_handler,
    project_not_found_handler,
    rate_limit_exceeded_handler,
    target_not_found_handler,
    unhandled_exception_handler,
)
from app.api.router import api_router
from app.core.logging import RequestContextLoggingMiddleware, configure_logging

configure_logging()

app = FastAPI(
    title="AegisAI",
    version="0.1.0",
    description="Open-source AI model security testing and evaluation platform",
)

app.add_middleware(RequestContextLoggingMiddleware)

app.add_exception_handler(ProjectNotFoundError, project_not_found_handler)
app.add_exception_handler(EmailAlreadyRegisteredError, email_already_registered_handler)
app.add_exception_handler(InvalidCredentialsError, invalid_credentials_handler)
app.add_exception_handler(AuthenticationRequiredError, authentication_required_handler)
app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
app.add_exception_handler(TargetNotFoundError, target_not_found_handler)
app.add_exception_handler(CredentialNotFoundError, credential_not_found_handler)
app.add_exception_handler(AssessmentNotFoundError, assessment_not_found_handler)
app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)
app.add_exception_handler(MembershipConflictError, membership_conflict_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Return the API root response."""

    return {
        "name": "AegisAI",
        "version": "0.1.0",
        "status": "ok",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Return basic liveness status for AegisAI.

    This endpoint performs no dependency checks and should only be used to
    confirm that the application process is running. Use
    ``/api/v1/system/ready`` to check dependency (database) health.
    """

    return {"status": "ok"}
