from types import SimpleNamespace
from uuid import UUID

from app.chat.repository import SupabaseChatRepository


class FakeQuery:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def insert(self, _payload):
        return self

    def update(self, _payload):
        return self

    def eq(self, _column, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self.rows_by_table = rows_by_table

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self.rows_by_table.get(name, []))


def test_create_thread_ignores_internal_supabase_columns() -> None:
    row = {
        "id": "00000000-0000-0000-0000-000000000002",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "title": "새 부산 여행 대화",
        "created_at": "2030-01-01T00:00:00Z",
        "updated_at": "2030-01-01T00:00:00Z",
    }
    repository = SupabaseChatRepository(FakeClient({"chat_threads": [row]}))

    thread = repository.create_thread(UUID(int=1))

    assert thread.id == UUID(int=2)
    assert thread.title == "새 부산 여행 대화"


def test_add_message_ignores_internal_supabase_columns() -> None:
    row = {
        "id": "00000000-0000-0000-0000-000000000003",
        "thread_id": "00000000-0000-0000-0000-000000000002",
        "role": "user",
        "content": "돼지국밥집 찾아줘",
        "structured_intent": None,
        "created_at": "2030-01-01T00:00:00Z",
    }
    repository = SupabaseChatRepository(FakeClient({"chat_messages": [row]}))

    message = repository.add_message(UUID(int=2), "user", "돼지국밥집 찾아줘")

    assert message.id == UUID(int=3)
    assert message.content == "돼지국밥집 찾아줘"

