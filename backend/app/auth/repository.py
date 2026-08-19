from datetime import datetime
from typing import Protocol
from uuid import UUID

from supabase import Client, create_client

from app.auth.models import StoredUser
from app.config import settings


class DuplicateUsernameError(Exception):
    pass


class AuthRepository(Protocol):
    def create_user(self, username: str, normalized_username: str, password_hash: str, display_name: str) -> StoredUser: ...
    def find_user(self, normalized_username: str) -> StoredUser | None: ...
    def create_session(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None: ...
    def find_user_by_session(self, token_hash: str, now: datetime) -> StoredUser | None: ...
    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None: ...


def _stored_user(row: dict) -> StoredUser:
    profile = row.get("user_profiles") or {}
    if isinstance(profile, list):
        profile = profile[0] if profile else {}
    return StoredUser(
        id=row["id"], username=row["username"], password_hash=row["password_hash"],
        is_active=row.get("is_active", True), display_name=profile.get("display_name", row["username"]),
    )


class SupabaseAuthRepository:
    def __init__(self, client: Client):
        self.client = client

    def create_user(self, username: str, normalized_username: str, password_hash: str, display_name: str) -> StoredUser:
        try:
            result = self.client.rpc("register_app_user", {
                "p_username": username, "p_normalized_username": normalized_username,
                "p_password_hash": password_hash, "p_display_name": display_name,
            }).execute()
        except Exception as error:
            if "unique" in str(error).lower() or "duplicate" in str(error).lower():
                raise DuplicateUsernameError from error
            raise
        return _stored_user(result.data[0])

    def find_user(self, normalized_username: str) -> StoredUser | None:
        result = self.client.table("app_users").select("id,username,password_hash,is_active,user_profiles(display_name)").eq("normalized_username", normalized_username).limit(1).execute()
        return _stored_user(result.data[0]) if result.data else None

    def create_session(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None:
        self.client.table("user_sessions").insert({"user_id": str(user_id), "token_hash": token_hash, "expires_at": expires_at.isoformat()}).execute()

    def find_user_by_session(self, token_hash: str, now: datetime) -> StoredUser | None:
        result = self.client.table("user_sessions").select("app_users(id,username,password_hash,is_active,user_profiles(display_name))").eq("token_hash", token_hash).is_("revoked_at", "null").gt("expires_at", now.isoformat()).limit(1).execute()
        if not result.data:
            return None
        user = result.data[0].get("app_users")
        return _stored_user(user) if user else None

    def revoke_session(self, token_hash: str, revoked_at: datetime) -> None:
        self.client.table("user_sessions").update({"revoked_at": revoked_at.isoformat()}).eq("token_hash", token_hash).execute()


def create_auth_repository() -> SupabaseAuthRepository:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY 설정이 필요합니다.")
    return SupabaseAuthRepository(create_client(settings.supabase_url, settings.supabase_service_role_key))
