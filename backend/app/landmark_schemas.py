from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LandmarkModel(BaseModel):
    """Strict contract for normalized landmark data inside the backend."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
        validate_default=True,
    )


class WarningItem(LandmarkModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


LandmarkQuery = Annotated[str, Field(min_length=1, max_length=200)]


class LandmarkSearchRequest(LandmarkModel):
    destination: str = Field(min_length=1, max_length=100)
    queries: list[LandmarkQuery] = Field(min_length=1, max_length=5)
    limit: int = Field(default=6, ge=1, le=10)


class ErrorDetail(LandmarkModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    request_id: str = Field(min_length=1, max_length=100)


class ErrorResponse(LandmarkModel):
    detail: ErrorDetail


class LandmarkCandidate(LandmarkModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=300)
    place_type: Literal["landmark"] = "landmark"
    category_name: str = Field(default="", max_length=500)
    address: str = Field(default="", max_length=500)
    road_address: str = Field(default="", max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    phone: str = Field(default="", max_length=100)
    kakao_place_url: str = Field(min_length=1, max_length=1000)


class LandmarkSearchResult(LandmarkModel):
    landmarks: list[LandmarkCandidate] = Field(default_factory=list, max_length=10)
    warnings: list[WarningItem] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def reject_duplicate_place_ids(self) -> "LandmarkSearchResult":
        place_ids = [landmark.id for landmark in self.landmarks]
        if len(place_ids) != len(set(place_ids)):
            raise ValueError("landmark ids must be unique")
        return self
