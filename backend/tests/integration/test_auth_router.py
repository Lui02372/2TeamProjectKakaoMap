from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.models import AuthUser, SessionResponse
from app.auth.service import InvalidCredentialsError, get_auth_service, require_current_session
from app.main import create_app


USER = AuthUser(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    username="busan02",
    display_name="부산 여행자",
)


class FakeAuthService:
    def signup(self, _request):
        return SessionResponse(access_token="signup-token", expires_at=datetime.now(UTC) + timedelta(days=7), user=USER)

    def login(self, request):
        if request.password == "wrong-password":
            raise InvalidCredentialsError
        return SessionResponse(access_token="login-token", expires_at=datetime.now(UTC) + timedelta(days=7), user=USER)

    def logout(self, _token):
        return None


def make_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    app.dependency_overrides[require_current_session] = lambda: USER
    return TestClient(app)


def test_signup_returns_bearer_session_without_email() -> None:
    response = make_client().post("/api/auth/signup", json={"username": "busan02", "password": "secure-password", "display_name": "부산 여행자"})
    assert response.status_code == 201
    assert response.json()["token_type"] == "bearer"
    assert response.json()["user"]["username"] == "busan02"
    assert "email" not in response.text


def test_login_uses_generic_error_for_bad_credentials() -> None:
    response = make_client().post("/api/auth/login", json={"username": "busan02", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "아이디 또는 비밀번호를 확인해 주세요."


def test_me_and_compatibility_verify_use_custom_session() -> None:
    client = make_client()
    assert client.get("/api/auth/me").json() == USER.model_dump(mode="json")
    assert client.get("/api/auth/session/verify").json() == USER.model_dump(mode="json")
