from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth.models import AuthUser
from app.auth.service import require_current_session
from app.places.models import SearchRequest, SearchResponse
from app.places.service import PlaceSearchService


place_router = APIRouter(prefix="/api/places", tags=["Places"])


def get_place_search_service(request: Request) -> PlaceSearchService:
    service = getattr(request.app.state, "place_search_service", None)
    if service is None:
        raise RuntimeError("Place search service is not initialized.")
    return service


@place_router.post("/search", response_model=SearchResponse)
async def search_places(
    payload: SearchRequest,
    _user: Annotated[AuthUser, Depends(require_current_session)],
    service: Annotated[PlaceSearchService, Depends(get_place_search_service)],
) -> SearchResponse:
    return await service.search(payload)
