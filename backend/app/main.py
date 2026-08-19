
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.clients.kakao_local_client import KakaoLocalClient
from app.config import settings
from app.exceptions import TravelBackendError
from app.landmark_schemas import ErrorDetail, ErrorResponse
from app.routers.agent_router import agent_router, structured_output_router
from app.routers.landmark_router import landmark_router
from app.routers.media_router import media_router
from app.routers.agent_router_food import router
from app.routers.auth_router import auth_router
from app.routers.place_router import place_router
from app.routers.chat_router import chat_router
from app.routers.favorite_router import favorite_router
from app.services.landmark_search_service import LandmarkSearchService
from app.places.service import PlaceSearchService


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own shared outbound HTTP resources for the application lifetime."""

    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        kakao_client = KakaoLocalClient.from_settings(http_client)
        application.state.landmark_search_service = (
            LandmarkSearchService.from_settings(kakao_client)
        )
        application.state.place_search_service = PlaceSearchService(
            kakao_client, search_size=min(15, settings.kakao_search_size)
        )
        try:
            yield
        finally:
            del application.state.landmark_search_service
            del application.state.place_search_service


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid4().hex)


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    payload = ErrorResponse(
        detail=ErrorDetail(
            code=code,
            message=message,
            request_id=_request_id(request),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


async def travel_backend_error_handler(
    request: Request,
    error: TravelBackendError,
) -> JSONResponse:
    """Convert safe domain errors without exposing upstream details."""

    return _error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.public_message,
    )


async def request_validation_error_handler(
    request: Request,
    _error: RequestValidationError,
) -> JSONResponse:
    """Return the same stable error envelope for invalid request bodies."""

    return _error_response(
        request,
        status_code=422,
        code="INVALID_REQUEST",
        message="The request body is invalid.",
    )


def create_app() -> FastAPI:
    """Create and configure the backend application."""

    application = FastAPI(
        title="Travel AI Backend",
        version="0.2.0",
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    application.add_exception_handler(
        TravelBackendError,
        travel_backend_error_handler,
    )
    application.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )

    application.include_router(agent_router)
    application.include_router(media_router)
    application.include_router(structured_output_router)
    application.include_router(landmark_router)
    application.include_router(router)
    application.include_router(auth_router)
    application.include_router(place_router)
    application.include_router(chat_router)
    application.include_router(favorite_router)
    return application


app = create_app()

#main.py
