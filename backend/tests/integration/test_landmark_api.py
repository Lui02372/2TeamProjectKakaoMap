from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.exceptions import (
    KakaoNotConfiguredError,
    KakaoUpstreamError,
    UpstreamTimeoutError,
)
from app.landmark_schemas import (
    LandmarkCandidate,
    LandmarkSearchResult,
    WarningItem,
)
from app.main import create_app
from app.routers.landmark_router import get_landmark_search_service


class FakeLandmarkSearchService:
    def __init__(
        self,
        *,
        result: LandmarkSearchResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or LandmarkSearchResult()
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        destination: str,
        queries: list[str],
        limit: int,
    ) -> LandmarkSearchResult:
        self.calls.append(
            {
                "destination": destination,
                "queries": queries,
                "limit": limit,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


@contextmanager
def client_for(
    service: FakeLandmarkSearchService,
) -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_landmark_search_service] = (
        lambda: service
    )
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()


def landmark_result() -> LandmarkSearchResult:
    return LandmarkSearchResult(
        landmarks=[
            LandmarkCandidate(
                id="8130788",
                name="Haeundae Beach",
                category_name="Travel > Attraction > Beach",
                address="Busan Haeundae-gu",
                road_address="264 Haeundaehaebyeon-ro, Busan",
                latitude=35.158698,
                longitude=129.160384,
                phone="",
                kakao_place_url="https://place.map.kakao.com/8130788",
            )
        ],
        warnings=[
            WarningItem(
                code="LANDMARK_RESULTS_INSUFFICIENT",
                message="Fewer landmarks were found than requested.",
            )
        ],
    )


def test_landmark_search_returns_grounded_result_and_forwards_input() -> None:
    service = FakeLandmarkSearchService(result=landmark_result())

    with client_for(service) as client:
        response = client.post(
            "/api/landmarks/search",
            json={
                "destination": "Busan",
                "queries": ["beach attractions", "representative landmarks"],
                "limit": 2,
            },
        )

    assert response.status_code == 200
    assert service.calls == [
        {
            "destination": "Busan",
            "queries": ["beach attractions", "representative landmarks"],
            "limit": 2,
        }
    ]
    assert response.json()["landmarks"][0]["id"] == "8130788"
    assert response.json()["landmarks"][0]["place_type"] == "landmark"
    assert response.json()["warnings"][0]["code"] == (
        "LANDMARK_RESULTS_INSUFFICIENT"
    )
    assert response.headers["x-request-id"]


@pytest.mark.parametrize(
    "payload",
    [
        {"destination": "", "queries": ["attractions"], "limit": 1},
        {"destination": "Busan", "queries": [], "limit": 1},
        {"destination": "Busan", "queries": [""], "limit": 1},
        {
            "destination": "Busan",
            "queries": ["1", "2", "3", "4", "5", "6"],
            "limit": 1,
        },
        {"destination": "Busan", "queries": ["attractions"], "limit": 0},
        {"destination": "Busan", "queries": ["attractions"], "limit": 11},
        {"destination": "Busan", "queries": ["attractions"], "limit": True},
        {
            "destination": "Busan",
            "queries": ["attractions"],
            "system_prompt": "user controlled",
        },
    ],
)
def test_landmark_search_rejects_invalid_request(
    payload: dict[str, object],
) -> None:
    service = FakeLandmarkSearchService()

    with client_for(service) as client:
        response = client.post("/api/landmarks/search", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_REQUEST"
    assert response.headers["x-request-id"] == (
        response.json()["detail"]["request_id"]
    )
    assert service.calls == []


@pytest.mark.parametrize(
    ("error_type", "status_code", "code"),
    [
        (KakaoNotConfiguredError, 503, "KAKAO_NOT_CONFIGURED"),
        (KakaoUpstreamError, 502, "KAKAO_UPSTREAM_ERROR"),
        (UpstreamTimeoutError, 504, "UPSTREAM_TIMEOUT"),
    ],
)
def test_landmark_search_maps_safe_domain_errors(
    error_type: type[Exception],
    status_code: int,
    code: str,
) -> None:
    service = FakeLandmarkSearchService(error=error_type())

    with client_for(service) as client:
        response = client.post(
            "/api/landmarks/search",
            json={
                "destination": "Busan",
                "queries": ["attractions"],
                "limit": 1,
            },
        )

    body = response.json()
    assert response.status_code == status_code
    assert body["detail"]["code"] == code
    assert body["detail"]["message"] == error_type.public_message
    assert response.headers["x-request-id"] == body["detail"]["request_id"]
    assert "api_key" not in response.text.lower()
    assert "authorization" not in response.text.lower()


def test_main_wiring_returns_503_without_kakao_key() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.post(
            "/api/landmarks/search",
            json={
                "destination": "Busan",
                "queries": ["attractions"],
                "limit": 1,
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "KAKAO_NOT_CONFIGURED"
