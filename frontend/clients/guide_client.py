from typing import Any

from core.api_client import request
from models.guide import ChatResponse, ChatThread, GuidePlace, SearchResponse, SessionData, UserProfile


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup(username: str, password: str, display_name: str) -> SessionData:
    return SessionData.model_validate(request("POST", "/api/auth/signup", json={"username": username, "password": password, "display_name": display_name}))


def login(username: str, password: str) -> SessionData:
    return SessionData.model_validate(request("POST", "/api/auth/login", json={"username": username, "password": password}))


def me(token: str) -> UserProfile:
    return UserProfile.model_validate(request("GET", "/api/auth/me", headers=_headers(token)))


def logout(token: str) -> None:
    request("POST", "/api/auth/logout", headers=_headers(token))


def create_thread(token: str) -> ChatThread:
    return ChatThread.model_validate(request("POST", "/api/chat/threads", headers=_headers(token)))


def ask(token: str, thread_id: str, message: str, district: str = "", category: str | None = None, quick_keyword: str = "") -> ChatResponse:
    payload: dict[str, Any] = {"message": message, "district": district, "quick_keyword": quick_keyword}
    if category:
        payload["category"] = category
    return ChatResponse.model_validate(request("POST", f"/api/chat/threads/{thread_id}/messages", json=payload, headers=_headers(token)))


def search(token: str, district: str = "", category: str = "all", keyword: str = "") -> SearchResponse:
    return SearchResponse.model_validate(request("POST", "/api/places/search", json={"district": district, "category": category, "keyword": keyword}, headers=_headers(token)))


def list_favorites(token: str) -> list[GuidePlace]:
    return [GuidePlace.model_validate(item) for item in request("GET", "/api/favorites", headers=_headers(token))]


def add_favorite(token: str, place_id: str) -> None:
    request("POST", f"/api/favorites/{place_id}", headers=_headers(token))


def delete_favorite(token: str, place_id: str) -> None:
    request("DELETE", f"/api/favorites/{place_id}", headers=_headers(token))
