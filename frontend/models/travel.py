"""여행 비교 응답 검증, 정규화 및 필터링."""

from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ProviderName = Literal["mock", "gemini", "openai", "ollama"]
PlaceType = Literal["landmark", "food"]


class TravelPlace(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = ""
    name: str = Field(min_length=1)
    place_type: PlaceType
    category_name: str = ""
    description: str = ""
    address: str = ""
    road_address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    phone: str = ""
    kakao_place_url: str = ""
    day: int = Field(default=1, ge=1, le=30)
    order: int = Field(default=1, ge=1, le=20)

    @model_validator(mode="before")
    @classmethod
    def map_kakao_coordinates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            normalized = dict(data)
            if normalized.get("latitude") in {None, ""}:
                normalized["latitude"] = normalized.get("y")
            if normalized.get("longitude") in {None, ""}:
                normalized["longitude"] = normalized.get("x")
            return normalized
        return data

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def tolerate_invalid_coordinates(cls, value: Any) -> float | None:
        if value in {None, ""}:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def has_valid_coordinates(self) -> bool:
        return (
            self.latitude is not None
            and self.longitude is not None
            and -90 <= self.latitude <= 90
            and -180 <= self.longitude <= 180
        )

    @property
    def safe_kakao_url(self) -> str:
        parsed = urlparse(self.kakao_place_url)
        return self.kakao_place_url if parsed.scheme in {"http", "https"} else ""


class TravelPlanContent(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    destination: str = Field(min_length=1)
    summary: str = ""
    nights: int = Field(ge=0, le=29)
    days: int = Field(ge=1, le=30)
    landmarks: list[TravelPlace] = Field(default_factory=list)
    foods: list[TravelPlace] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_trip(self) -> "TravelPlanContent":
        if self.days != self.nights + 1:
            raise ValueError("여행 일수는 숙박 일수보다 1일 많아야 합니다.")
        for place in self.landmarks:
            place.place_type = "landmark"
        for place in self.foods:
            place.place_type = "food"
        if any(place.day > self.days for place in [*self.landmarks, *self.foods]):
            raise ValueError("장소 방문 일차는 전체 여행 일수를 넘을 수 없습니다.")
        return self

    def normalized_places(self) -> list[TravelPlace]:
        unique: dict[str, TravelPlace] = {}
        for place in [*self.landmarks, *self.foods]:
            key = place.id or (
                f"{place.name.casefold()}|{place.latitude}|{place.longitude}"
            )
            unique.setdefault(key, place)
        return sorted(unique.values(), key=lambda item: (item.day, item.order, item.name))


class ProviderTravelResult(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    provider: ProviderName
    status: Literal["success", "error"]
    model: str = ""
    latency_ms: float = Field(default=0, ge=0)
    content: TravelPlanContent | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ProviderTravelResult":
        if self.status == "success" and self.content is None:
            raise ValueError("성공 결과에는 content가 필요합니다.")
        if self.status == "error" and not self.error:
            raise ValueError("실패 결과에는 error가 필요합니다.")
        return self


class TravelCompareResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request_count: int = Field(ge=1, le=4)
    landmark_count: int = Field(ge=1, le=10)
    food_count: int = Field(ge=1, le=10)
    results: list[ProviderTravelResult] = Field(min_length=1, max_length=4)

    @property
    def successful_results(self) -> list[ProviderTravelResult]:
        return [item for item in self.results if item.status == "success"]


def build_compare_payload(
    message: str,
    providers: list[str],
    landmark_count: int,
    food_count: int,
) -> dict[str, Any]:
    cleaned_message = message.strip()
    if not cleaned_message:
        raise ValueError("여행 요청을 입력해 주세요.")
    unique_providers = list(dict.fromkeys(providers))
    allowed = {"mock", "gemini", "openai", "ollama"}
    if not unique_providers or len(unique_providers) > 4:
        raise ValueError("Provider를 1개 이상 4개 이하로 선택해 주세요.")
    if any(provider not in allowed for provider in unique_providers):
        raise ValueError("지원하지 않는 Provider가 포함되어 있습니다.")
    counts = (landmark_count, food_count)
    if any(isinstance(count, bool) or int(count) != count for count in counts):
        raise ValueError("추천 개수는 정수여야 합니다.")
    if not 1 <= int(landmark_count) <= 10 or not 1 <= int(food_count) <= 10:
        raise ValueError("추천 개수는 1~10이어야 합니다.")
    return {
        "message": cleaned_message,
        "providers": unique_providers,
        "landmark_count": int(landmark_count),
        "food_count": int(food_count),
    }


def filter_places(
    places: list[TravelPlace], day: int | None, place_type: str
) -> list[TravelPlace]:
    return [
        place
        for place in places
        if (day is None or place.day == day)
        and (place_type == "all" or place.place_type == place_type)
    ]
