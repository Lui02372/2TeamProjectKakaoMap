from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.models import AuthUser
from app.auth.service import require_current_session
from app.favorites.repository import PlaceNotFoundError, SupabaseFavoriteRepository, create_favorite_repository
from app.places.models import GuidePlace


favorite_router = APIRouter(prefix="/api/favorites", tags=["Favorites"])


def get_favorite_repository() -> SupabaseFavoriteRepository:
    return create_favorite_repository()


@favorite_router.get("", response_model=list[GuidePlace])
def list_favorites(user: Annotated[AuthUser, Depends(require_current_session)], repository: Annotated[SupabaseFavoriteRepository, Depends(get_favorite_repository)]) -> list[GuidePlace]:
    return repository.list(user.id)


@favorite_router.post("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(place_id: UUID, user: Annotated[AuthUser, Depends(require_current_session)], repository: Annotated[SupabaseFavoriteRepository, Depends(get_favorite_repository)]) -> Response:
    try:
        repository.add(user.id, place_id)
    except PlaceNotFoundError as error:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다.") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@favorite_router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_favorite(place_id: UUID, user: Annotated[AuthUser, Depends(require_current_session)], repository: Annotated[SupabaseFavoriteRepository, Depends(get_favorite_repository)]) -> Response:
    repository.delete(user.id, place_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
