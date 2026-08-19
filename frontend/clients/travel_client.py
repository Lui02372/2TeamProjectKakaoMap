"""여행 계획 비교 API를 호출하는 얇은 클라이언트."""

from typing import Any

from core.api_client import request
from models.travel import TravelCompareResponse, build_compare_payload


def compare_travel_plans(
    message: str,
    providers: list[str],
    landmark_count: int = 6,
    food_count: int = 4,
) -> TravelCompareResponse:
    payload = build_compare_payload(message, providers, landmark_count, food_count)
    response: Any = request("POST", "/api/travel-plans/compare", json=payload)
    return TravelCompareResponse.model_validate(response)
