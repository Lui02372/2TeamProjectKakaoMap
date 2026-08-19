from datetime import UTC, datetime
from uuid import UUID

from supabase import Client, create_client

from app.chat.models import ChatMessage, ChatThread
from app.config import settings
from app.places.models import GuidePlace, SearchIntent


class ThreadNotFoundError(Exception):
    pass


class SupabaseChatRepository:
    def __init__(self, client: Client):
        self.client = client

    def create_thread(self, user_id: UUID) -> ChatThread:
        result = self.client.table("chat_threads").insert({"user_id": str(user_id)}).execute()
        return ChatThread.model_validate(result.data[0])

    def list_threads(self, user_id: UUID) -> list[ChatThread]:
        result = self.client.table("chat_threads").select("id,title,created_at,updated_at").eq("user_id", str(user_id)).order("updated_at", desc=True).execute()
        return [ChatThread.model_validate(row) for row in result.data]

    def require_thread(self, user_id: UUID, thread_id: UUID) -> None:
        result = self.client.table("chat_threads").select("id").eq("id", str(thread_id)).eq("user_id", str(user_id)).limit(1).execute()
        if not result.data:
            raise ThreadNotFoundError

    def list_messages(self, user_id: UUID, thread_id: UUID) -> list[ChatMessage]:
        self.require_thread(user_id, thread_id)
        result = self.client.table("chat_messages").select("id,role,content,structured_intent,created_at").eq("thread_id", str(thread_id)).order("created_at").execute()
        return [ChatMessage.model_validate(row) for row in result.data]

    def add_message(self, thread_id: UUID, role: str, content: str, intent: SearchIntent | None = None) -> ChatMessage:
        payload = {"thread_id": str(thread_id), "role": role, "content": content, "structured_intent": intent.model_dump() if intent else None}
        result = self.client.table("chat_messages").insert(payload).execute()
        self.client.table("chat_threads").update({"updated_at": datetime.now(UTC).isoformat()}).eq("id", str(thread_id)).execute()
        return ChatMessage.model_validate(result.data[0])

    def record_search(self, message_id: UUID, intent: SearchIntent, places: list[GuidePlace]) -> None:
        search = self.client.table("place_searches").insert({
            "message_id": str(message_id), "region": "부산", "district": intent.district,
            "category": intent.category, "keyword": intent.keyword,
        }).execute().data[0]
        if places:
            self.client.table("search_results").insert([
                {"search_id": search["id"], "place_id": str(place.id), "result_rank": rank}
                for rank, place in enumerate(places, 1)
            ]).execute()


def create_chat_repository() -> SupabaseChatRepository:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY 설정이 필요합니다.")
    return SupabaseChatRepository(create_client(settings.supabase_url, settings.supabase_service_role_key))
