"""Supabase Auth access-token verification using public signing keys."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient

from app.config import settings


class InvalidSessionError(ValueError):
    """Raised when a bearer token cannot be accepted as a Supabase session."""


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str


_bearer_scheme = HTTPBearer(auto_error=False)


def verify_access_token(token: str, jwk_client: PyJWKClient) -> CurrentUser:
    """Verify a Supabase Auth JWT with the project's public JWKS."""

    if not settings.supabase_url:
        raise InvalidSessionError("SUPABASE_URL is not configured.")

    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=settings.supabase_jwt_audience,
            issuer=f"{settings.supabase_url}/auth/v1",
        )
        subject = claims.get("sub")
        if not isinstance(subject, str):
            raise InvalidSessionError("Session token is missing a subject.")
        return CurrentUser(
            id=UUID(subject),
            email=str(claims.get("email", "")),
        )
    except (InvalidTokenError, ValueError) as error:
        if isinstance(error, InvalidSessionError):
            raise
        raise InvalidSessionError("Session token is invalid.") from error


def public_jwk_client() -> PyJWKClient:
    """Build a verifier from the public Supabase signing-key discovery URL."""

    if not settings.supabase_jwks_url:
        raise InvalidSessionError("SUPABASE_JWKS_URL is not configured.")
    return PyJWKClient(settings.supabase_jwks_url)


def require_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> CurrentUser:
    """FastAPI dependency implementation for bearer-token protected routes."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication is required.")
    try:
        return verify_access_token(credentials.credentials, public_jwk_client())
    except InvalidSessionError as error:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from error
