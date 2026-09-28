"""Authentication API routes for AegisAI."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.security.dependencies import CurrentUser
from app.security.rate_limit import enforce_login_rate_limit, enforce_register_rate_limit
from app.security.tokens import create_access_token
from app.services.audit import record_audit_event
from app.services.auth import authenticate_user, register_user

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

DatabaseSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_register_rate_limit)],
)
async def register_endpoint(
    payload: UserCreate,
    session: DatabaseSession,
) -> UserResponse:
    """Register a new user account."""

    user = register_user(session, payload)

    record_audit_event(
        session,
        actor_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=str(user.id),
    )

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
async def login_endpoint(
    payload: LoginRequest,
    session: DatabaseSession,
) -> TokenResponse:
    """Authenticate a user and issue an access token."""

    user = authenticate_user(session, payload.email, payload.password)

    access_token, expires_in = create_access_token(user.id)

    record_audit_event(
        session,
        actor_id=user.id,
        action="user.login",
        resource_type="user",
        resource_id=str(user.id),
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
async def me_endpoint(
    current_user: CurrentUser,
) -> UserResponse:
    """Return the currently authenticated user."""

    return UserResponse.model_validate(current_user)
