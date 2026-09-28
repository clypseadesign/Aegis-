"""JWT access token utilities for AegisAI.

Uses PyJWT exclusively. Never implement token signing or verification
manually.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings


class InvalidTokenError(Exception):
    """Raised when a JWT access token is missing, invalid, or expired."""


def create_access_token(user_id: UUID) -> tuple[str, int]:
    """Create a signed JWT access token for the given user ID.

    Returns a tuple of (encoded token, lifetime in seconds). Raises
    RuntimeError if SECRET_KEY has not been configured, since signing a
    token with an empty key would be insecure.
    """

    settings = get_settings()

    if not settings.secret_key.strip():
        raise RuntimeError("SECRET_KEY must be configured to issue access tokens.")

    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_delta,
    }

    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> UUID:
    """Decode and validate a JWT access token, returning the subject user ID."""

    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid or expired access token.") from exc

    subject = payload.get("sub")

    if not subject:
        raise InvalidTokenError("Access token is missing a subject.")

    try:
        return UUID(str(subject))
    except ValueError as exc:
        raise InvalidTokenError("Access token subject is not a valid user ID.") from exc
