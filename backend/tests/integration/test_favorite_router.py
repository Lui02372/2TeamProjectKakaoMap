from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.models import AuthUser
from app.auth.service import require_current_session
from app.main import create_app
from app.routers.favorite_router import get_favorite_repository


class FakeFavorites:
    def __init__(self):
        self.saved = set()

    def list(self, user_id):
        return []

    def add(self, user_id, place_id):
        self.saved.add((user_id, place_id))

    def delete(self, user_id, place_id):
        self.saved.discard((user_id, place_id))


def test_favorite_add_list_delete_is_user_scoped_and_idempotent() -> None:
    user = AuthUser(id=UUID(int=1), username="busan02", display_name="여행자")
    place_id = UUID(int=5)
    repository = FakeFavorites()
    app = create_app()
    app.dependency_overrides[require_current_session] = lambda: user
    app.dependency_overrides[get_favorite_repository] = lambda: repository
    client = TestClient(app)

    assert client.post(f"/api/favorites/{place_id}").status_code == 204
    assert client.post(f"/api/favorites/{place_id}").status_code == 204
    assert repository.saved == {(user.id, place_id)}
    assert client.get("/api/favorites").json() == []
    assert client.delete(f"/api/favorites/{place_id}").status_code == 204
    assert repository.saved == set()
