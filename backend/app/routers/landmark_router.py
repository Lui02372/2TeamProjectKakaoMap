from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.landmark_schemas import (
    ErrorResponse,
    LandmarkSearchRequest,
    LandmarkSearchResult,
)
from app.services.landmark_search_service import LandmarkSearchService


landmark_router = APIRouter(
    prefix="/api/landmarks",
    tags=["Landmarks"],
)


def get_landmark_search_service(request: Request) -> LandmarkSearchService:
    """Return the application-scoped Landmark search service."""

    service = getattr(request.app.state, "landmark_search_service", None)
    if service is None:
        raise RuntimeError("Landmark search service is not initialized.")
    return service


@landmark_router.post(
    "/search",
    response_model=LandmarkSearchResult,
    summary="Search verified Kakao landmarks",
    responses={
        422: {"model": ErrorResponse, "description": "Invalid request"},
        502: {"model": ErrorResponse, "description": "Kakao upstream error"},
        503: {"model": ErrorResponse, "description": "Kakao is not configured"},
        504: {"model": ErrorResponse, "description": "Kakao request timed out"},
    },
)
async def search_landmarks(
    payload: LandmarkSearchRequest,
    service: Annotated[
        LandmarkSearchService,
        Depends(get_landmark_search_service),
    ],
) -> LandmarkSearchResult:
    """Search Kakao Local and return normalized landmark candidates."""

    return await service.search(
        destination=payload.destination,
        queries=payload.queries,
        limit=payload.limit,
    )
