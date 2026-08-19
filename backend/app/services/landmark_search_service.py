from __future__ import annotations

import asyncio
from collections.abc import Sequence
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.clients.kakao_local_client import KakaoLocalClient
from app.exceptions import TravelBackendError
from app.kakao_schemas import KakaoPlaceDocument
from app.landmark_schemas import (
    LandmarkCandidate,
    LandmarkSearchResult,
    WarningItem,
)


LANDMARK_CATEGORY_CODE = "AT4"
KAKAO_PLACE_HOST = "place.map.kakao.com"
REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "서울특별시": ("서울",),
    "부산광역시": ("부산",),
    "대구광역시": ("대구",),
    "인천광역시": ("인천",),
    "광주광역시": ("광주",),
    "대전광역시": ("대전",),
    "울산광역시": ("울산",),
    "세종특별자치시": ("세종",),
    "경기도": ("경기",),
    "강원특별자치도": ("강원",),
    "충청북도": ("충북",),
    "충청남도": ("충남",),
    "전북특별자치도": ("전북",),
    "전라북도": ("전북",),
    "전라남도": ("전남",),
    "경상북도": ("경북",),
    "경상남도": ("경남",),
    "제주특별자치도": ("제주",),
}


class LandmarkSearchService:
    """Search and normalize Kakao tourism results without creating itinerary data."""

    def __init__(
        self,
        client: KakaoLocalClient,
        *,
        max_concurrency: int = 3,
        search_size: int = 15,
    ) -> None:
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int):
            raise ValueError("max_concurrency must be an integer")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if isinstance(search_size, bool) or not isinstance(search_size, int):
            raise ValueError("search_size must be an integer")
        if not 1 <= search_size <= 15:
            raise ValueError("search_size must be between 1 and 15")

        self._client = client
        self._max_concurrency = max_concurrency
        self._search_size = search_size

    @classmethod
    def from_settings(
        cls,
        client: KakaoLocalClient,
        *,
        max_concurrency: int = 3,
    ) -> "LandmarkSearchService":
        """Build a service with the configured Kakao search size."""

        from app.config import settings

        return cls(
            client,
            max_concurrency=max_concurrency,
            search_size=settings.kakao_search_size,
        )

    async def search(
        self,
        destination: str,
        queries: Sequence[str],
        limit: int,
    ) -> LandmarkSearchResult:
        normalized_destination = self._validate_destination(destination)
        normalized_queries = self._normalize_queries(normalized_destination, queries)
        self._validate_limit(limit)

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def run_query(
            query: str,
        ) -> tuple[list[KakaoPlaceDocument], Exception | None]:
            async with semaphore:
                try:
                    documents = await self._client.search_keyword(
                        query=query,
                        category_group_code=LANDMARK_CATEGORY_CODE,
                        size=self._search_size,
                    )
                    return documents, None
                except TravelBackendError as error:
                    return [], error

        # asyncio.gather returns results in awaitable order, even if calls finish
        # out of order. Flattening below therefore preserves Kakao accuracy order
        # within the caller's original query order.
        outcomes = await asyncio.gather(
            *(run_query(query) for query in normalized_queries)
        )
        failures = [error for _, error in outcomes if error is not None]
        if len(failures) == len(outcomes):
            raise failures[0]

        warnings: list[WarningItem] = []
        if failures:
            warnings.append(
                WarningItem(
                    code="LANDMARK_SEARCH_PARTIAL_FAILURE",
                    message="일부 관광명소 검색에 실패했습니다.",
                )
            )

        landmarks: list[LandmarkCandidate] = []
        seen_ids: set[str] = set()
        invalid_count = 0

        for documents, error in outcomes:
            if error is not None:
                continue
            for document in documents:
                if document.category_group_code != LANDMARK_CATEGORY_CODE:
                    continue
                if not self._matches_destination(document, normalized_destination):
                    continue
                if document.id in seen_ids:
                    continue

                candidate = self._to_candidate(document)
                if candidate is None:
                    invalid_count += 1
                    continue

                seen_ids.add(candidate.id)
                landmarks.append(candidate)
                if len(landmarks) == limit:
                    break
            if len(landmarks) == limit:
                break

        if invalid_count:
            warnings.append(
                WarningItem(
                    code="INVALID_LANDMARK_RESULT",
                    message="유효하지 않은 관광명소 검색 결과를 제외했습니다.",
                )
            )

        if not landmarks:
            warnings.append(
                WarningItem(
                    code="LANDMARK_RESULTS_EMPTY",
                    message="조건에 맞는 관광명소를 찾지 못했습니다.",
                )
            )
        elif len(landmarks) < limit:
            warnings.append(
                WarningItem(
                    code="LANDMARK_RESULTS_INSUFFICIENT",
                    message="요청한 수보다 적은 관광명소를 찾았습니다.",
                )
            )

        return LandmarkSearchResult(landmarks=landmarks, warnings=warnings)

    @staticmethod
    def _validate_destination(destination: str) -> str:
        if not isinstance(destination, str):
            raise ValueError("destination must be a string")
        normalized = " ".join(destination.split())
        if not normalized:
            raise ValueError("destination must not be empty")
        if len(normalized) > 100:
            raise ValueError("destination must not exceed 100 characters")
        return normalized

    @staticmethod
    def _normalize_queries(destination: str, queries: Sequence[str]) -> list[str]:
        if isinstance(queries, (str, bytes)) or not isinstance(queries, Sequence):
            raise ValueError("queries must be a sequence of strings")
        if not 1 <= len(queries) <= 5:
            raise ValueError("queries must contain between 1 and 5 items")

        normalized_queries: list[str] = []
        seen: set[str] = set()
        destination_key = destination.casefold()

        for query in queries:
            if not isinstance(query, str):
                raise ValueError("each query must be a string")
            normalized = " ".join(query.split())
            if not normalized:
                raise ValueError("queries must not contain empty items")
            if not normalized.casefold().startswith(destination_key):
                normalized = f"{destination} {normalized}"

            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized_queries.append(normalized)

        return normalized_queries

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")

    @staticmethod
    def _matches_destination(
        document: KakaoPlaceDocument,
        destination: str,
    ) -> bool:
        destination_keys = {
            destination.casefold(),
            *(alias.casefold() for alias in REGION_ALIASES.get(destination, ())),
        }
        return any(
            destination_key in address.casefold()
            for address in (document.address_name, document.road_address_name)
            if address
            for destination_key in destination_keys
        )

    @staticmethod
    def _to_candidate(
        document: KakaoPlaceDocument,
    ) -> LandmarkCandidate | None:
        if not LandmarkSearchService._is_valid_kakao_place_url(document.place_url):
            return None

        try:
            return LandmarkCandidate(
                id=document.id,
                name=document.place_name,
                category_name=document.category_name,
                address=document.address_name,
                road_address=document.road_address_name,
                latitude=float(document.y),
                longitude=float(document.x),
                phone=document.phone,
                kakao_place_url=document.place_url,
            )
        except (TypeError, ValueError, ValidationError):
            return None

    @staticmethod
    def _is_valid_kakao_place_url(value: str) -> bool:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except (TypeError, ValueError):
            return False

        return (
            parsed.scheme.casefold() in {"http", "https"}
            and parsed.hostname == KAKAO_PLACE_HOST
            and parsed.username is None
            and parsed.password is None
            and port in {None, 80, 443}
        )
