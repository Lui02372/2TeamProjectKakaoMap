"""Async client for the Kakao Local keyword-search API."""

from __future__ import annotations

import asyncio
from typing import Final
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.exceptions import (
    InvalidKakaoResponseError,
    KakaoNotConfiguredError,
    KakaoUpstreamError,
    UpstreamTimeoutError,
)
from app.kakao_schemas import KakaoKeywordResponse, KakaoPlaceDocument


_KEYWORD_SEARCH_PATH: Final = "/v2/local/search/keyword.json"
_RETRYABLE_STATUS_CODES: Final = {429, *range(500, 600)}
_SUPPORTED_CATEGORY_GROUP_CODES: Final = {"AT4", "FD6"}
_KAKAO_LOCAL_HOST: Final = "dapi.kakao.com"
_ALLOWED_KAKAO_NETLOCS: Final = {
    _KAKAO_LOCAL_HOST,
    f"{_KAKAO_LOCAL_HOST}:443",
}


class KakaoLocalClient:
    """Small, injectable wrapper around Kakao Local's keyword search."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        api_key: str,
        base_url: str = "https://dapi.kakao.com",
        timeout: float = 5.0,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.1,
    ) -> None:
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError("timeout must be greater than zero")
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or not 0 <= max_retries <= 3
        ):
            raise ValueError("max_retries must be between 0 and 3")
        if (
            isinstance(retry_delay_seconds, bool)
            or not isinstance(retry_delay_seconds, (int, float))
            or retry_delay_seconds < 0
        ):
            raise ValueError("retry_delay_seconds must not be negative")

        normalized_base_url = self._validate_base_url(base_url)

        self._http_client = http_client
        self._api_key = api_key.strip()
        self._base_url = normalized_base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

    @classmethod
    def from_settings(cls, http_client: httpx.AsyncClient) -> "KakaoLocalClient":
        """Build a client from the application's Kakao settings."""

        from app.config import settings

        return cls(
            http_client,
            api_key=settings.kakao_rest_api_key,
            base_url=settings.kakao_local_base_url,
            timeout=settings.kakao_request_timeout_seconds,
            max_retries=settings.kakao_max_retries,
        )

    async def search_keyword(
        self,
        query: str,
        category_group_code: str,
        size: int = 15,
    ) -> list[KakaoPlaceDocument]:
        """Return validated Kakao documents in the API's accuracy order."""

        if not self._api_key:
            raise KakaoNotConfiguredError()
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be empty")
        if category_group_code not in _SUPPORTED_CATEGORY_GROUP_CODES:
            raise ValueError("category_group_code must be AT4 or FD6")
        if not 1 <= size <= 15:
            raise ValueError("size must be between 1 and 15")

        url = f"{self._base_url}{_KEYWORD_SEARCH_PATH}"
        headers = {"Authorization": f"KakaoAK {self._api_key}"}
        params = {
            "query": query.strip(),
            "category_group_code": category_group_code,
            "size": size,
            "sort": "accuracy",
        }

        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http_client.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self._timeout,
                )
            except httpx.TimeoutException:
                raise UpstreamTimeoutError() from None
            except httpx.HTTPError:
                raise KakaoUpstreamError() from None

            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt < self._max_retries:
                    await self._wait_before_retry()
                    continue
                raise KakaoUpstreamError()

            if not 200 <= response.status_code < 300:
                raise KakaoUpstreamError()

            break

        if response is None:  # pragma: no cover - defensive invariant
            raise KakaoUpstreamError()

        try:
            payload = response.json()
            parsed = KakaoKeywordResponse.model_validate(payload)
        except (ValueError, ValidationError):
            raise InvalidKakaoResponseError() from None

        return parsed.documents

    async def _wait_before_retry(self) -> None:
        if self._retry_delay_seconds:
            await asyncio.sleep(self._retry_delay_seconds)

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        error_message = "base_url must be https://dapi.kakao.com"
        if not isinstance(base_url, str) or base_url != base_url.strip():
            raise ValueError(error_message)

        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except (TypeError, ValueError):
            raise ValueError(error_message) from None

        is_allowed = (
            parsed.scheme.lower() == "https"
            and parsed.hostname == _KAKAO_LOCAL_HOST
            and parsed.netloc.lower() in _ALLOWED_KAKAO_NETLOCS
            and parsed.username is None
            and parsed.password is None
            and port in (None, 443)
            and parsed.path in ("", "/")
            and not parsed.query
            and not parsed.fragment
            and "?" not in base_url
            and "#" not in base_url
        )
        if not is_allowed:
            raise ValueError(error_message)

        return f"https://{_KAKAO_LOCAL_HOST}" + (":443" if port == 443 else "")
