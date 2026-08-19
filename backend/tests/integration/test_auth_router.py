from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.supabase_auth import CurrentUser, require_current_user


def test_session_verify_returns_jwks_verified_user_identity() -> None:
    app = create_app()
    app.dependency_overrides[require_current_user] = lambda: CurrentUser(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="user@example.com",
    )

    response = TestClient(app).get("/api/auth/session/verify")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "user@example.com",
    }
