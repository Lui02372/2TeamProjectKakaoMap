from datetime import UTC, datetime, timedelta
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import AuthUser, LoginRequest, SessionResponse, SignupRequest, StoredUser
from app.auth.password import hash_password, hash_session_token, normalize_username, verify_password
from app.auth.repository import AuthRepository, create_auth_repository
from app.config import settings


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, repository: AuthRepository, ttl_hours: int = 168):
        self.repository = repository
        self.ttl_hours = ttl_hours

    def _issue(self, user: StoredUser) -> SessionResponse:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(hours=self.ttl_hours)
        self.repository.create_session(user.id, hash_session_token(token), expires_at)
        return SessionResponse(access_token=token, expires_at=expires_at, user=AuthUser.model_validate(user))

    def signup(self, request: SignupRequest) -> SessionResponse:
        username = normalize_username(request.username)
        user = self.repository.create_user(username, username, hash_password(request.password), request.display_name)
        return self._issue(user)

    def login(self, request: LoginRequest) -> SessionResponse:
        user = self.repository.find_user(normalize_username(request.username))
        if not user or not user.is_active or not verify_password(user.password_hash, request.password):
            raise InvalidCredentialsError
        return self._issue(user)

    def authenticate(self, token: str) -> AuthUser:
        user = self.repository.find_user_by_session(hash_session_token(token), datetime.now(UTC))
        if not user or not user.is_active:
            raise InvalidCredentialsError
        return AuthUser.model_validate(user)

    def logout(self, token: str) -> None:
        self.repository.revoke_session(hash_session_token(token), datetime.now(UTC))


def get_auth_service() -> AuthService:
    return AuthService(create_auth_repository(), settings.session_ttl_hours)


_bearer = HTTPBearer(auto_error=False)


def get_bearer_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return credentials.credentials


def require_current_session(token: Annotated[str, Depends(get_bearer_token)], service: Annotated[AuthService, Depends(get_auth_service)]) -> AuthUser:
    try:
        return service.authenticate(token)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="로그인 세션이 만료되었습니다.") from error
