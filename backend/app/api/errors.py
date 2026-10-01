"""Centralized API exception handling for AegisAI."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.schemas import APIError, APIErrorResponse

_logger = logging.getLogger("aegis.security")


class ProjectNotFoundError(Exception):
    """Raised when a requested project does not exist."""

    def __init__(self) -> None:
        super().__init__("Project not found.")


class TargetNotFoundError(Exception):
    """Raised when a requested target does not exist."""

    def __init__(self) -> None:
        super().__init__("Target not found.")


class CredentialNotFoundError(Exception):
    """Raised when a requested target credential does not exist."""

    def __init__(self) -> None:
        super().__init__("Credential not found.")


class AssessmentNotFoundError(Exception):
    """Raised when a requested assessment resource (test, execution, etc.) does not exist."""

    def __init__(self) -> None:
        super().__init__("Resource not found.")


class ExecutionBindingError(Exception):
    """Raised when a test and target exist but cannot be paired for a run.

    Distinct from ``AssessmentNotFoundError``: the resources are real, the
    combination is not runnable. Carries a message so the caller learns which
    of provider, target status, or capabilities is the problem.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmailAlreadyRegisteredError(Exception):
    """Raised when attempting to register an email that is already in use."""

    def __init__(self) -> None:
        super().__init__("A user with this email is already registered.")


class InvalidCredentialsError(Exception):
    """Raised when login credentials are missing, unknown, or incorrect."""

    def __init__(self) -> None:
        super().__init__("Incorrect email or password.")


class AuthenticationRequiredError(Exception):
    """Raised when a request requires authentication but none was provided."""

    def __init__(self) -> None:
        super().__init__("Authentication is required to access this resource.")


class PermissionDeniedError(Exception):
    """Raised when an authenticated user's role does not permit an action."""

    def __init__(self) -> None:
        super().__init__("You do not have permission to perform this action.")


def _client_host(request: Request) -> str:
    """Return the connecting client's host for logging, without any secrets."""

    return request.client.host if request.client is not None else "unknown"


class RateLimitExceededError(Exception):
    """Raised when a client exceeds the allowed request rate for an endpoint."""

    def __init__(self, retry_after_seconds: int = 60) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Too many requests. Please try again later.")


class MembershipConflictError(Exception):
    """Raised when a membership operation would leave a project without an admin."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "This action would leave the project without an administrator. "
            "Assign another admin before removing your own or the last remaining admin."
        )


async def project_not_found_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when a project does not exist."""

    error = APIError(
        code="PROJECT_NOT_FOUND",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=404,
        content=response.model_dump(),
    )


async def target_not_found_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when a target does not exist."""

    error = APIError(
        code="TARGET_NOT_FOUND",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=404,
        content=response.model_dump(),
    )


async def credential_not_found_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when a credential does not exist."""

    error = APIError(
        code="CREDENTIAL_NOT_FOUND",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=404,
        content=response.model_dump(),
    )


async def assessment_not_found_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when an assessment resource does not exist."""

    error = APIError(
        code="ASSESSMENT_NOT_FOUND",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=404,
        content=response.model_dump(),
    )


async def execution_binding_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when a test/target pairing is unrunnable."""

    error = APIError(
        code="EXECUTION_BINDING_INVALID",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=422,
        content=response.model_dump(),
    )


async def email_already_registered_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when an email is already registered."""

    error = APIError(
        code="EMAIL_ALREADY_REGISTERED",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=409,
        content=response.model_dump(),
    )


async def invalid_credentials_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response for failed login attempts."""

    _logger.warning(
        "authentication failed",
        extra={"path": request.url.path, "client_host": _client_host(request)},
    )

    error = APIError(
        code="INVALID_CREDENTIALS",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=401,
        content=response.model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authentication_required_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when authentication is missing or invalid."""

    _logger.warning(
        "authentication required",
        extra={"path": request.url.path, "client_host": _client_host(request)},
    )

    error = APIError(
        code="AUTHENTICATION_REQUIRED",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=401,
        content=response.model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def permission_denied_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when a user's role forbids an action."""

    _logger.warning(
        "permission denied",
        extra={"path": request.url.path, "client_host": _client_host(request)},
    )

    error = APIError(
        code="PERMISSION_DENIED",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=403,
        content=response.model_dump(),
    )


async def rate_limit_exceeded_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standardized response when a client exceeds a rate limit."""

    retry_after = getattr(exc, "retry_after_seconds", 60)

    error = APIError(
        code="RATE_LIMIT_EXCEEDED",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=429,
        content=response.model_dump(),
        headers={"Retry-After": str(retry_after)},
    )


async def membership_conflict_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a 409 when a membership operation conflicts with admin invariants."""

    error = APIError(
        code="MEMBERSHIP_CONFLICT",
        message=str(exc),
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=409,
        content=response.model_dump(),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a safe response for unexpected application exceptions."""

    error = APIError(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
    )

    response = APIErrorResponse(error=error)

    return JSONResponse(
        status_code=500,
        content=response.model_dump(),
    )
