from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


PlaceCategory = Literal["food", "cafe", "attraction", "shopping", "all"]


class GuideModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchRequest(GuideModel):
    district: str = Field(default="", max_length=40)
    category: PlaceCategory = "all"
    keyword: str = Field(default="", max_length=100)
    limit: int = Field(default=10, ge=1, le=15)


class SearchIntent(GuideModel):
    region: str = "부산"
    district: str = ""
    category: PlaceCategory = "all"
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
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    phone: str = ""
    kakao_place_url: str
    is_favorite: bool = False


class SearchResponse(GuideModel):
    intent: SearchIntent
    places: list[GuidePlace] = Field(default_factory=list)
    warning: str = ""
