from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.models import AuthUser, LoginRequest, SessionResponse, SignupRequest
from app.auth.repository import DuplicateUsernameError
from app.auth.service import AuthService, InvalidCredentialsError, get_auth_service, get_bearer_token, require_current_session


auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@auth_router.post("/signup", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest, service: Annotated[AuthService, Depends(get_auth_service)]) -> SessionResponse:
    try:
        return service.signup(request)
    except DuplicateUsernameError as error:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.") from error


@auth_router.post("/login", response_model=SessionResponse)
def login(request: LoginRequest, service: Annotated[AuthService, Depends(get_auth_service)]) -> SessionResponse:
    try:
        return service.login(request)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호를 확인해 주세요.") from error


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: Annotated[str, Depends(get_bearer_token)], service: Annotated[AuthService, Depends(get_auth_service)]) -> Response:
    service.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.get("/me", response_model=AuthUser)
@auth_router.get("/session/verify", response_model=AuthUser)
def me(user: Annotated[AuthUser, Depends(require_current_session)]) -> AuthUser:
    return user
