from app.auth.password import (
    hash_password,
    hash_session_token,
    normalize_username,
    verify_password,
)


def test_password_is_stored_as_argon2id_and_verifies() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("$argon2id$")
    assert "correct horse battery staple" not in encoded
    assert verify_password(encoded, "correct horse battery staple") is True
    assert verify_password(encoded, "wrong password") is False


def test_username_normalization_is_stable() -> None:
    assert normalize_username("  Busan_02  ") == "busan_02"


def test_session_token_hash_never_contains_token() -> None:
    token = "visible-session-token"
    digest = hash_session_token(token)

    assert len(digest) == 64
    assert token not in digest

