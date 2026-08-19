from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.places.models import GuidePlace, PlaceCategory, SearchIntent


class ChatModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChatThread(ChatModel):
    id: UUID
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChatMessage(ChatModel):
    id: UUID
    role: str
    content: str
    structured_intent: SearchIntent | None = None
    created_at: datetime | None = None


class ChatMessageRequest(ChatModel):
    message: str = Field(min_length=1, max_length=2000)
    district: str = Field(default="", max_length=40)
    category: PlaceCategory | None = None
    quick_keyword: str = Field(default="", max_length=100)


class ChatResponse(ChatModel):
    thread_id: UUID
    answer: str
    intent: SearchIntent
    places: list[GuidePlace] = Field(default_factory=list)
    warning: str = ""
