import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from app.exceptions import KakaoUpstreamError, UpstreamTimeoutError
from app.kakao_schemas import KakaoPlaceDocument
from app.services.landmark_search_service import LandmarkSearchService


@dataclass
class FakeResponse:
    value: list[KakaoPlaceDocument] | Exception
    delay: float = 0


class FakeKakaoClient:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def search_keyword(
        self,
        query: str,
        category_group_code: str,
        size: int = 15,
    ) -> list[KakaoPlaceDocument]:
        self.calls.append(
            {
                "query": query,
                "category_group_code": category_group_code,
                "size": size,
            }
        )
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        response = self.responses[query]
        try:
            await asyncio.sleep(response.delay)
            if isinstance(response.value, Exception):
                raise response.value
            return response.value
        finally:
            self.active_calls -= 1


def place(
    place_id: str,
    name: str,
    *,
    category_group_code: str = "AT4",
    address: str = "부산 해운대구 우동",
    road_address: str = "부산 해운대구 해운대해변로 264",
    x: str = "129.1604",
    y: str = "35.1587",
    place_url: str | None = None,
) -> KakaoPlaceDocument:
    return KakaoPlaceDocument(
        id=place_id,
        place_name=name,
        category_name="여행 > 관광명소",
        category_group_code=category_group_code,
        category_group_name="관광명소",
        address_name=address,
        road_address_name=road_address,
        x=x,
        y=y,
        phone="",
        place_url=place_url or f"https://place.map.kakao.com/{place_id}",
        distance="",
    )


def warning_codes(result: Any) -> set[str]:
    return {warning.code for warning in result.warnings}


def test_search_normalizes_queries_maps_coordinates_and_deduplicates_ids() -> None:
    client = FakeKakaoClient(
        {
            "부산 해변 관광지": FakeResponse(
                [place("1", "해운대"), place("2", "광안리")], delay=0.01
            ),
            "부산 대표 명소": FakeResponse(
                [place("2", "광안리 중복"), place("3", "감천문화마을")]
            ),
        }
    )
    service = LandmarkSearchService(client, search_size=12)

    result = asyncio.run(
        service.search(
            "  부산  ",
            [" 해변   관광지 ", "부산 대표 명소", "해변 관광지"],
            3,
        )
    )

    assert [call["query"] for call in client.calls] == [
        "부산 해변 관광지",
        "부산 대표 명소",
    ]
    assert all(call["category_group_code"] == "AT4" for call in client.calls)
    assert all(call["size"] == 12 for call in client.calls)
    assert [item.id for item in result.landmarks] == ["1", "2", "3"]
    assert result.landmarks[0].latitude == 35.1587
    assert result.landmarks[0].longitude == 129.1604
    assert result.warnings == []


def test_search_preserves_query_order_and_bounds_concurrency() -> None:
    client = FakeKakaoClient(
        {
            "부산 첫째": FakeResponse([place("1", "첫째")], delay=0.03),
            "부산 둘째": FakeResponse([place("2", "둘째")], delay=0),
            "부산 셋째": FakeResponse([place("3", "셋째")], delay=0),
        }
    )
    service = LandmarkSearchService(client, max_concurrency=2)

    result = asyncio.run(service.search("부산", ["첫째", "둘째", "셋째"], 3))

    assert [item.id for item in result.landmarks] == ["1", "2", "3"]
    assert client.max_active_calls == 2


def test_partial_failure_returns_safe_warning_and_valid_results() -> None:
    client = FakeKakaoClient(
        {
            "부산 실패": FakeResponse(KakaoUpstreamError()),
            "부산 성공": FakeResponse([place("1", "해운대")]),
        }
    )

    result = asyncio.run(
        LandmarkSearchService(client).search("부산", ["실패", "성공"], 1)
    )

    assert [item.id for item in result.landmarks] == ["1"]
    assert "LANDMARK_SEARCH_PARTIAL_FAILURE" in warning_codes(result)
    assert KakaoUpstreamError.public_message not in " ".join(
        warning.message for warning in result.warnings
    )


def test_all_query_failures_propagate_first_input_order_error() -> None:
    first_error = KakaoUpstreamError()
    client = FakeKakaoClient(
        {
            "부산 첫째": FakeResponse(first_error, delay=0.02),
            "부산 둘째": FakeResponse(UpstreamTimeoutError(), delay=0),
        }
    )

    with pytest.raises(KakaoUpstreamError) as captured:
        asyncio.run(
            LandmarkSearchService(client).search("부산", ["첫째", "둘째"], 1)
        )

    assert captured.value is first_error


def test_unexpected_programming_error_is_not_converted_to_warning() -> None:
    client = FakeKakaoClient(
        {
            "부산 오류": FakeResponse(RuntimeError("programming bug")),
            "부산 성공": FakeResponse([place("1", "해운대")]),
        }
    )

    with pytest.raises(RuntimeError, match="programming bug"):
        asyncio.run(
            LandmarkSearchService(client).search("부산", ["오류", "성공"], 1)
        )


@pytest.mark.parametrize(
    ("destination", "address"),
    [
        ("부산광역시", "부산 해운대구 우동"),
        ("서울특별시", "서울 종로구 세종로"),
        ("제주특별자치도", "제주 제주시 애월읍"),
    ],
)
def test_search_matches_common_official_region_names_to_short_addresses(
    destination: str,
    address: str,
) -> None:
    query = f"{destination} 명소"
    client = FakeKakaoClient(
        {query: FakeResponse([place("1", "대표 명소", address=address, road_address="")])}
    )

    result = asyncio.run(
        LandmarkSearchService(client).search(destination, ["명소"], 1)
    )

    assert [item.id for item in result.landmarks] == ["1"]
    assert result.warnings == []


def test_search_filters_destination_and_category_and_drops_invalid_results() -> None:
    client = FakeKakaoClient(
        {
            "부산 명소": FakeResponse(
                [
                    place("wrong-city", "서울 명소", address="서울 종로구", road_address=""),
                    place("wrong-category", "음식점", category_group_code="FD6"),
                    place("bad-coordinate", "좌표 오류", x="not-a-number"),
                    place(
                        "bad-url",
                        "URL 오류",
                        place_url="https://place.map.kakao.com.evil.example/1",
                    ),
                ]
            )
        }
    )

    result = asyncio.run(
        LandmarkSearchService(client).search("부산", ["명소"], 2)
    )

    assert result.landmarks == []
    assert warning_codes(result) == {
        "INVALID_LANDMARK_RESULT",
        "LANDMARK_RESULTS_EMPTY",
    }


def test_search_warns_when_fewer_results_than_requested() -> None:
    client = FakeKakaoClient(
        {"부산 명소": FakeResponse([place("1", "해운대")])}
    )

    result = asyncio.run(
        LandmarkSearchService(client).search("부산", ["명소"], 2)
    )

    assert [item.id for item in result.landmarks] == ["1"]
    assert warning_codes(result) == {"LANDMARK_RESULTS_INSUFFICIENT"}


def test_from_settings_uses_configured_search_size(monkeypatch) -> None:
    client = FakeKakaoClient(
        {"부산 명소": FakeResponse([place("1", "해운대")])}
    )
    monkeypatch.setattr(
        "app.config.settings",
        SimpleNamespace(kakao_search_size=7),
    )

    service = LandmarkSearchService.from_settings(client)
    result = asyncio.run(service.search("부산", ["명소"], 1))

    assert [item.id for item in result.landmarks] == ["1"]
    assert client.calls[0]["size"] == 7


@pytest.mark.parametrize(
    ("destination", "queries", "limit"),
    [
        ("", ["명소"], 1),
        ("부산", [], 1),
        ("부산", [""], 1),
        ("부산", ["1", "2", "3", "4", "5", "6"], 1),
        ("부산", ["명소"], 0),
        ("부산", ["명소"], 11),
        ("부산", ["명소"], True),
    ],
)
def test_search_rejects_invalid_inputs(
    destination: str,
    queries: list[str],
    limit: int,
) -> None:
    client = FakeKakaoClient({})

    with pytest.raises(ValueError):
        asyncio.run(
            LandmarkSearchService(client).search(destination, queries, limit)
        )

    assert client.calls == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_concurrency": 0}, "max_concurrency"),
        ({"max_concurrency": True}, "max_concurrency"),
        ({"search_size": 0}, "search_size"),
        ({"search_size": 16}, "search_size"),
    ],
)
def test_constructor_rejects_invalid_limits(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LandmarkSearchService(FakeKakaoClient({}), **kwargs)
