from uuid import UUID

from app.chat.intent_service import IntentService
from app.chat.models import ChatMessage, ChatMessageRequest, ChatResponse, ChatThread
from app.chat.repository import SupabaseChatRepository
from app.places.models import SearchIntent, SearchRequest
from app.places.service import PlaceSearchService


class ChatService:
    def __init__(self, repository: SupabaseChatRepository, intent_service: IntentService, place_service: PlaceSearchService):
        self.repository = repository
        self.intent_service = intent_service
        self.place_service = place_service

    def create_thread(self, user_id: UUID) -> ChatThread:
        return self.repository.create_thread(user_id)

    def list_threads(self, user_id: UUID) -> list[ChatThread]:
        return self.repository.list_threads(user_id)

    def list_messages(self, user_id: UUID, thread_id: UUID) -> list[ChatMessage]:
        return self.repository.list_messages(user_id, thread_id)

    async def ask(self, user_id: UUID, thread_id: UUID, request: ChatMessageRequest) -> ChatResponse:
        previous = self.repository.list_messages(user_id, thread_id)
        recent_intents = [item.structured_intent for item in previous if item.structured_intent]
        user_message = self.repository.add_message(thread_id, "user", request.message)
        intent, ai_warning = self.intent_service.interpret(
            request.message, recent_intents, district=request.district,
            category=request.category, quick_keyword=request.quick_keyword,
        )
        search = await self.place_service.search(SearchRequest(
            district=intent.district, category=intent.category, keyword=intent.keyword,
        ))
        intent = search.intent
        if search.places:
            names = ", ".join(place.name for place in search.places[:3])
            answer = f"{intent.district or '부산'}에서 요청에 맞는 장소를 찾았어요. 먼저 {names}을(를) 살펴보세요."
        else:
            answer = "조건에 맞는 부산 장소를 찾지 못했어요. 지역이나 키워드를 조금 바꿔 볼까요?"
        self.repository.add_message(thread_id, "assistant", answer, intent)
        self.repository.record_search(user_message.id, intent, search.places)
        warning = " ".join(item for item in (ai_warning, search.warning) if item)
        return ChatResponse(thread_id=thread_id, answer=answer, intent=intent, places=search.places, warning=warning)
