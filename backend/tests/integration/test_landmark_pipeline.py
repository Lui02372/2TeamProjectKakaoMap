import asyncio

import httpx

from app.clients.kakao_local_client import KakaoLocalClient
from app.services.landmark_search_service import LandmarkSearchService


def test_kakao_response_is_grounded_into_landmark_candidates() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["query"] == "부산 해변 관광명소"
            assert request.url.params["category_group_code"] == "AT4"
            return httpx.Response(
                200,
                json={
                    "meta": {
                        "total_count": 1,
                        "pageable_count": 1,
                        "is_end": True,
                        "same_name": {
                            "keyword": "해변 관광명소",
                            "region": ["부산광역시"],
                            "selected_region": "부산광역시",
                        },
                    },
                    "documents": [
                        {
                            "id": "8130788",
                            "place_name": "해운대해수욕장",
                            "category_name": "여행 > 관광명소 > 해수욕장",
                            "category_group_code": "AT4",
                            "category_group_name": "관광명소",
                            "phone": "",
                            "address_name": "부산 해운대구 우동",
                            "road_address_name": "부산 해운대구 해운대해변로 264",
                            "x": "129.160384",
                            "y": "35.158698",
                            "place_url": "https://place.map.kakao.com/8130788",
                            "distance": "",
                        }
                    ],
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with http_client:
            kakao_client = KakaoLocalClient(
                http_client,
                api_key="test-rest-api-key",
                retry_delay_seconds=0,
            )
            service = LandmarkSearchService(
                kakao_client,
                search_size=10,
            )
            result = await service.search(
                destination="부산",
                queries=["해변 관광명소"],
                limit=1,
            )

        assert result.warnings == []
        assert len(result.landmarks) == 1
        landmark = result.landmarks[0]
        assert landmark.id == "8130788"
        assert landmark.name == "해운대해수욕장"
        assert landmark.place_type == "landmark"
        assert landmark.latitude == 35.158698
        assert landmark.longitude == 129.160384
        assert landmark.kakao_place_url == "https://place.map.kakao.com/8130788"

    asyncio.run(scenario())
