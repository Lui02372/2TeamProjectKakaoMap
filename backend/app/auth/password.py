import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


_hasher = PasswordHasher()


def normalize_username(username: str) -> str:
    return username.strip().lower()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return _hasher.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
