from pydantic import BaseModel, Field

from app.places.models import GuidePlace


class FavoriteList(BaseModel):
    places: list[GuidePlace] = Field(default_factory=list)
