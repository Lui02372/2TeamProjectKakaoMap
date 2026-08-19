from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.models import AuthUser
from app.auth.service import require_current_session
from app.main import create_app
from app.places.models import SearchIntent, SearchResponse
from app.routers.place_router import get_place_search_service


class FakeSearchService:
    async def search(self, request):
        return SearchResponse(intent=SearchIntent(region="부산", district=request.district, category=request.category, keyword=request.keyword, query="부산 서면 맛집"), places=[])


def test_place_search_requires_session_and_returns_intent() -> None:
    app = create_app()
    app.dependency_overrides[require_current_session] = lambda: AuthUser(id=UUID(int=1), username="busan02", display_name="여행자")
    app.dependency_overrides[get_place_search_service] = lambda: FakeSearchService()
    response = TestClient(app).post("/api/places/search", json={"district": "서면", "category": "food", "keyword": "맛집"})

    assert response.status_code == 200
    assert response.json()["intent"]["district"] == "서면"

