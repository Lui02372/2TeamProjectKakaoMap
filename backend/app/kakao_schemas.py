from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


KakaoCategoryGroupCode = Literal["AT4", "FD6", "CE7", ""]


class KakaoRawModel(BaseModel):
    """Strict contract for data received from Kakao Local."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
        validate_default=True,
    )


class KakaoPlaceDocument(KakaoRawModel):
    id: str = Field(min_length=1, max_length=100)
    place_name: str = Field(min_length=1, max_length=300)
    category_name: str = Field(default="", max_length=500)
    category_group_code: KakaoCategoryGroupCode = ""
    category_group_name: str = Field(default="", max_length=100)
    address_name: str = Field(default="", max_length=500)
    road_address_name: str = Field(default="", max_length=500)
    x: str = Field(min_length=1, max_length=50)
    y: str = Field(min_length=1, max_length=50)
    phone: str = Field(default="", max_length=100)
    place_url: str = Field(min_length=1, max_length=1000)
    distance: str = Field(default="", max_length=50)


class KakaoSameName(KakaoRawModel):
    keyword: str = Field(default="", max_length=300)
    region: list[str] = Field(default_factory=list, max_length=100)
    selected_region: str = Field(default="", max_length=300)


class KakaoKeywordMeta(KakaoRawModel):
    total_count: int = Field(ge=0)
    pageable_count: int = Field(ge=0)
    is_end: bool
    same_name: KakaoSameName | None = None


class KakaoKeywordResponse(KakaoRawModel):
    meta: KakaoKeywordMeta
    documents: list[KakaoPlaceDocument] = Field(max_length=15)
