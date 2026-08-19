from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.password import normalize_username


class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    username: str = Field(min_length=4, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=40)

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        return normalize_username(value)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)


class AuthUser(BaseModel):
    id: UUID
    username: str
    display_name: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: AuthUser


class StoredUser(AuthUser):
    password_hash: str
    is_active: bool = True
