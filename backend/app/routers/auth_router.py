"""Authenticated session introspection routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.supabase_auth import CurrentUser, require_current_user


auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@auth_router.get("/session/verify")
def verify_session(
    user: Annotated[CurrentUser, Depends(require_current_user)],
) -> dict[str, str]:
    """Return the identity encoded in a valid Supabase Auth JWT."""

    return {"user_id": str(user.id), "email": user.email}
