import pytest
from pydantic import ValidationError

from app.auth.models import SignupRequest


def test_signup_accepts_four_character_educational_password() -> None:
    request = SignupRequest(username="id01", password="pw01", display_name="부산 여행자 1")

    assert request.password == "pw01"


def test_signup_rejects_password_shorter_than_four_characters() -> None:
    with pytest.raises(ValidationError):
        SignupRequest(username="id01", password="pw1", display_name="부산 여행자 1")

