from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.models import AuthUser
from app.auth.service import require_current_session
from app.chat.models import ChatResponse, ChatThread
from app.main import create_app
from app.places.models import SearchIntent
from app.routers.chat_router import get_chat_service


class FakeChatService:
    def create_thread(self, user_id):
        return ChatThread(id=UUID(int=2), title="새 부산 여행 대화")

    async def ask(self, user_id, thread_id, request):
        return ChatResponse(thread_id=thread_id, answer="서면 맛집을 찾아봤어요.", intent=SearchIntent(district="서면", category="food", keyword="고기", query="부산 서면 고기 맛집"), places=[])


def test_create_thread_and_send_ai_question() -> None:
    app = create_app()
    app.dependency_overrides[require_current_session] = lambda: AuthUser(id=UUID(int=1), username="busan02", display_name="여행자")
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
    client = TestClient(app)

    created = client.post("/api/chat/threads")
    answer = client.post(f"/api/chat/threads/{created.json()['id']}/messages", json={"message": "서면 고기 맛집 알려줘"})

    assert created.status_code == 201
    assert answer.status_code == 200
    assert answer.json()["intent"]["district"] == "서면"
