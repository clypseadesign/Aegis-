"""Authentication dependencies for AegisAI API routes."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import AuthenticationRequiredError
from app.db.session import get_db_session
from app.models.user import User
from app.security.tokens import InvalidTokenError, decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[Session, Depends(get_db_session)],
) -> User:
    """Resolve the current authenticated user from a bearer access token.

    Raises AuthenticationRequiredError when no token is supplied, the token
    is invalid or expired, or the referenced user no longer exists or has
    been deactivated.
    """

    if credentials is None:
        raise AuthenticationRequiredError()

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise AuthenticationRequiredError() from exc

    user = session.get(User, user_id)

    if user is None or not user.is_active:
        raise AuthenticationRequiredError()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


__all__ = ["CurrentUser", "get_current_user"]
