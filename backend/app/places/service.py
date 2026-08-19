from urllib.parse import urlsplit

from pydantic import ValidationError

from app.clients.kakao_local_client import KakaoLocalClient
from app.kakao_schemas import KakaoPlaceDocument
from app.places.models import GuidePlace, SearchIntent, SearchRequest, SearchResponse
from app.places.repository import PlaceRepository, create_place_repository


CATEGORY_GROUPS = {"food": "FD6", "cafe": "CE7", "attraction": "AT4", "shopping": "", "all": ""}
CATEGORY_WORDS = {"food": "맛집", "cafe": "카페", "attraction": "관광지", "shopping": "쇼핑", "all": "장소"}


class PlaceSearchService:
    def __init__(self, client: KakaoLocalClient, repository: PlaceRepository | None = None, *, search_size: int = 10):
        self.client = client
        self.repository = repository
        self.search_size = search_size

    async def search(self, request: SearchRequest) -> SearchResponse:
        terms = ["부산", request.district, request.keyword, CATEGORY_WORDS[request.category]]
        query = " ".join(dict.fromkeys(term.strip() for term in terms if term.strip()))
        group = CATEGORY_GROUPS[request.category]
        documents = await self.client.search_keyword(query, group, min(request.limit, self.search_size))
        rows: list[dict] = []
        seen: set[str] = set()
        for document in documents:
            if document.id in seen or not self._is_busan(document):
                continue
            row = self._to_row(document)
            if row is None:
                continue
            seen.add(document.id)
            rows.append(row)
            if len(rows) == request.limit:
                break
        repository = self.repository or create_place_repository()
        persisted = repository.upsert_places(rows)
        public_fields = GuidePlace.model_fields.keys()
        places = [
            GuidePlace.model_validate({key: row[key] for key in public_fields if key in row})
            for row in persisted
        ]
        warning = "" if places else "조건에 맞는 부산 장소를 찾지 못했어요. 지역이나 키워드를 바꿔 보세요."
        return SearchResponse(
            intent=SearchIntent(district=request.district, category=request.category, keyword=request.keyword, query=query),
            places=places,
            warning=warning,
        )

    @staticmethod
    def _is_busan(document: KakaoPlaceDocument) -> bool:
        return any("부산" in value for value in (document.address_name, document.road_address_name))

    @staticmethod
    def _to_row(document: KakaoPlaceDocument) -> dict | None:
        try:
            parsed = urlsplit(document.place_url)
            if parsed.scheme not in {"http", "https"} or parsed.hostname != "place.map.kakao.com":
                return None
            kakao_place_url = f"https://place.map.kakao.com{parsed.path}"
            latitude, longitude = float(document.y), float(document.x)
            GuidePlace(
                id="00000000-0000-0000-0000-000000000000", kakao_place_id=document.id,
                name=document.place_name, latitude=latitude, longitude=longitude,
                kakao_place_url=kakao_place_url,
            )
        except (TypeError, ValueError, ValidationError):
            return None
        return {
            "kakao_place_id": document.id, "name": document.place_name,
            "category_name": document.category_name, "category_group_code": document.category_group_code,
            "address": document.address_name, "road_address": document.road_address_name,
            "latitude": latitude, "longitude": longitude, "phone": document.phone,
            "kakao_place_url": kakao_place_url, "raw_snapshot": document.model_dump(mode="json"),
        }
