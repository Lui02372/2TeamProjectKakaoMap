from uuid import UUID

from supabase import Client, create_client

from app.config import settings
from app.places.models import GuidePlace


class PlaceNotFoundError(Exception):
    pass


class SupabaseFavoriteRepository:
    def __init__(self, client: Client):
        self.client = client

    def list(self, user_id: UUID) -> list[GuidePlace]:
        fields = "id,kakao_place_id,name,category_name,category_group_code,address,road_address,latitude,longitude,phone,kakao_place_url"
        result = self.client.table("favorite_places").select(f"places({fields})").eq("user_id", str(user_id)).order("created_at", desc=True).execute()
        return [GuidePlace.model_validate({**row["places"], "is_favorite": True}) for row in result.data if row.get("places")]

    def add(self, user_id: UUID, place_id: UUID) -> None:
        place = self.client.table("places").select("id").eq("id", str(place_id)).limit(1).execute()
        if not place.data:
            raise PlaceNotFoundError
        self.client.table("favorite_places").upsert({"user_id": str(user_id), "place_id": str(place_id)}, on_conflict="user_id,place_id").execute()

    def delete(self, user_id: UUID, place_id: UUID) -> None:
        self.client.table("favorite_places").delete().eq("user_id", str(user_id)).eq("place_id", str(place_id)).execute()


def create_favorite_repository() -> SupabaseFavoriteRepository:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY 설정이 필요합니다.")
    return SupabaseFavoriteRepository(create_client(settings.supabase_url, settings.supabase_service_role_key))
