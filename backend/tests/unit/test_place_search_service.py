import asyncio
from uuid import UUID

from app.kakao_schemas import KakaoPlaceDocument
from app.places.models import SearchRequest
from app.places.service import PlaceSearchService


def kakao(place_id: str, name: str, address: str = "부산 부산진구 부전동") -> KakaoPlaceDocument:
    return KakaoPlaceDocument(
        id=place_id, place_name=name, category_name="음식점 > 한식",
        category_group_code="FD6", category_group_name="음식점",
        address_name=address, road_address_name="", x="129.059", y="35.157",
        phone="051-000-0000", place_url=f"https://place.map.kakao.com/{place_id}", distance="",
    )


class FakeKakao:
    def __init__(self):
        self.calls = []

    async def search_keyword(self, query, category_group_code, size=15):
        self.calls.append((query, category_group_code, size))
        return [kakao("1", "부산식당"), kakao("1", "중복"), kakao("2", "서울식당", "서울 강남구")]


class FakeRepository:
    def upsert_places(self, places):
        return [{**place, "id": UUID(int=index + 1)} for index, place in enumerate(places)]


def test_search_builds_filter_query_and_returns_only_unique_busan_places() -> None:
    client = FakeKakao()
    service = PlaceSearchService(client, FakeRepository(), search_size=10)

    result = asyncio.run(service.search(SearchRequest(district="서면", category="food", keyword="고기")))

    assert client.calls == [("부산 서면 고기 맛집", "FD6", 10)]
    assert [place.kakao_place_id for place in result.places] == ["1"]
    assert result.places[0].latitude == 35.157
    assert result.places[0].longitude == 129.059


def test_explicit_category_maps_to_kakao_group() -> None:
    client = FakeKakao()
    service = PlaceSearchService(client, FakeRepository())

    asyncio.run(service.search(SearchRequest(category="cafe", keyword="오션뷰")))

    assert client.calls[0][1] == "CE7"

