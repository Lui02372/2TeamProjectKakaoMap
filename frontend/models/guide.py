from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GuideModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class UserProfile(GuideModel):
    id: UUID
    username: str
    display_name: str


class SessionData(GuideModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserProfile


class SearchIntent(GuideModel):
    region: str = "부산"
    district: str = ""
    category: Literal["food", "cafe", "attraction", "shopping", "all"] = "all"
    keyword: str = ""
    query: str = ""


class GuidePlace(GuideModel):
    id: UUID
    kakao_place_id: str
    name: str
    category_name: str = ""
    category_group_code: str = ""
    address: str = ""
    road_address: str = ""
    latitude: float
    longitude: float
    phone: str = ""
    kakao_place_url: str = ""
    is_favorite: bool = False

    @property
    def safe_kakao_url(self) -> str:
        parsed = urlparse(self.kakao_place_url)
        return self.kakao_place_url if parsed.scheme in {"http", "https"} and parsed.hostname == "place.map.kakao.com" else ""


class SearchResponse(GuideModel):
    intent: SearchIntent
    places: list[GuidePlace] = Field(default_factory=list)
    warning: str = ""


class ChatThread(GuideModel):
    id: UUID
    title: str


class ChatResponse(SearchResponse):
    thread_id: UUID
    answer: str
