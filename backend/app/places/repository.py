from typing import Protocol

from supabase import Client, create_client

from app.config import settings


class PlaceRepository(Protocol):
    def upsert_places(self, places: list[dict]) -> list[dict]: ...


class SupabasePlaceRepository:
    def __init__(self, client: Client):
        self.client = client

    def upsert_places(self, places: list[dict]) -> list[dict]:
        if not places:
            return []
        result = self.client.table("places").upsert(places, on_conflict="kakao_place_id").execute()
        by_kakao_id = {row["kakao_place_id"]: row for row in result.data}
        return [by_kakao_id[item["kakao_place_id"]] for item in places if item["kakao_place_id"] in by_kakao_id]


def create_place_repository() -> SupabasePlaceRepository:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY 설정이 필요합니다.")
    return SupabasePlaceRepository(create_client(settings.supabase_url, settings.supabase_service_role_key))
