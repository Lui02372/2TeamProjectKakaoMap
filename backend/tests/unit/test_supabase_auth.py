from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import supabase_auth


class FakeJwkClient:
    def get_signing_key_from_jwt(self, token: str):
        assert token == "signed.jwt"
        return SimpleNamespace(key="public-key")


def test_verify_access_token_uses_public_jwks_and_returns_current_user(monkeypatch):
    captured: dict[str, object] = {}

    def fake_decode(token, key, **kwargs):
        captured.update(token=token, key=key, **kwargs)
        return {"sub": "00000000-0000-0000-0000-000000000001", "email": "user@example.com"}

    monkeypatch.setattr(supabase_auth.jwt, "decode", fake_decode)
    monkeypatch.setattr(
        supabase_auth,
        "settings",
        SimpleNamespace(
            supabase_url="https://project.supabase.co",
            supabase_jwt_audience="authenticated",
        ),
    )

    user = supabase_auth.verify_access_token("signed.jwt", FakeJwkClient())

    assert user.id == UUID("00000000-0000-0000-0000-000000000001")
    assert user.email == "user@example.com"
    assert captured == {
        "token": "signed.jwt",
        "key": "public-key",
        "algorithms": ["ES256", "RS256"],
        "audience": "authenticated",
        "issuer": "https://project.supabase.co/auth/v1",
    }


def test_verify_access_token_rejects_token_without_subject(monkeypatch):
    monkeypatch.setattr(supabase_auth.jwt, "decode", lambda *args, **kwargs: {"email": "user@example.com"})
    monkeypatch.setattr(
        supabase_auth,
        "settings",
        SimpleNamespace(
            supabase_url="https://project.supabase.co",
            supabase_jwt_audience="authenticated",
        ),
    )

    with pytest.raises(supabase_auth.InvalidSessionError, match="subject"):
        supabase_auth.verify_access_token("signed.jwt", FakeJwkClient())


def test_require_current_user_rejects_missing_bearer_token():
    with pytest.raises(HTTPException) as error:
        supabase_auth.require_current_user(None)

    assert error.value.status_code == 401


def test_require_current_user_verifies_present_bearer_token(monkeypatch):
    expected = supabase_auth.CurrentUser(UUID(int=1), "user@example.com")
    monkeypatch.setattr(supabase_auth, "public_jwk_client", lambda: FakeJwkClient())
    monkeypatch.setattr(supabase_auth, "verify_access_token", lambda token, client: expected)

    result = supabase_auth.require_current_user(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed.jwt")
    )

    assert result == expected
