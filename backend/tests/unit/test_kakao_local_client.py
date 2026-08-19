from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace

import httpx
import pytest

from app.clients.kakao_local_client import KakaoLocalClient
from app.exceptions import (
    InvalidKakaoResponseError,
    KakaoNotConfiguredError,
    KakaoUpstreamError,
    UpstreamTimeoutError,
)


API_KEY = "test-rest-api-key"


def _valid_payload() -> dict:
    return {
        "meta": {
            "is_end": True,
            "pageable_count": 1,
            "same_name": {
                "keyword": "부산 관광명소",
                "region": [],
                "selected_region": "부산광역시",
            },
            "total_count": 1,
        },
        "documents": [
            {
                "address_name": "부산 해운대구 우동",
                "category_group_code": "AT4",
                "category_group_name": "관광명소",
                "category_name": "여행 > 관광명소 > 해수욕장",
                "distance": "",
                "id": "8130788",
                "phone": "",
                "place_name": "해운대해수욕장",
                "place_url": "https://place.map.kakao.com/8130788",
                "road_address_name": "부산 해운대구 해운대해변로 264",
                "x": "129.160384",
                "y": "35.158698",
            }
        ],
    }


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    **overrides,
) -> tuple[KakaoLocalClient, httpx.AsyncClient]:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    options = {
        "api_key": API_KEY,
        "base_url": "https://dapi.kakao.com/",
        "timeout": 2.5,
        "max_retries": 1,
        "retry_delay_seconds": 0,
    }
    options.update(overrides)
    return KakaoLocalClient(http_client, **options), http_client


def test_search_keyword_sends_expected_request_and_returns_documents() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v2/local/search/keyword.json"
            assert request.url.params["query"] == "부산 대표 관광지"
            assert request.url.params["category_group_code"] == "AT4"
            assert request.url.params["size"] == "6"
            assert request.url.params["sort"] == "accuracy"
            assert request.headers["Authorization"] == f"KakaoAK {API_KEY}"
            return httpx.Response(200, json=_valid_payload())

        client, http_client = _client(handler)
        async with http_client:
            documents = await client.search_keyword("부산 대표 관광지", "AT4", 6)

        assert len(documents) == 1
        assert documents[0].id == "8130788"
        assert documents[0].place_name == "해운대해수욕장"

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [0, 16])
def test_search_keyword_rejects_size_outside_kakao_range(size: int) -> None:
    async def scenario() -> None:
        client, http_client = _client(
            lambda _: pytest.fail("invalid size must not make an HTTP request")
        )
        async with http_client:
            with pytest.raises(ValueError, match="between 1 and 15"):
                await client.search_keyword("부산", "AT4", size)

    asyncio.run(scenario())


def test_missing_api_key_does_not_make_request() -> None:
    async def scenario() -> None:
        client, http_client = _client(
            lambda _: pytest.fail("missing configuration must not make a request"),
            api_key="   ",
        )
        async with http_client:
            with pytest.raises(KakaoNotConfiguredError):
                await client.search_keyword("부산", "AT4")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("query", "category_group_code", "message"),
    [
        ("", "AT4", "query must not be empty"),
        ("   ", "AT4", "query must not be empty"),
        ("부산", "", "category_group_code must be AT4 or FD6"),
        ("부산", "CE7", "category_group_code must be AT4 or FD6"),
    ],
)
def test_invalid_search_input_does_not_make_request(
    query: str,
    category_group_code: str,
    message: str,
) -> None:
    async def scenario() -> None:
        client, http_client = _client(
            lambda _: pytest.fail("invalid input must not make an HTTP request")
        )
        async with http_client:
            with pytest.raises(ValueError, match=message):
                await client.search_keyword(query, category_group_code)

    asyncio.run(scenario())


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_retryable_status_is_retried_then_succeeds(status_code: int) -> None:
    async def scenario() -> None:
        attempts = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(status_code, text=f"secret {API_KEY}")
            return httpx.Response(200, json=_valid_payload())

        client, http_client = _client(handler)
        async with http_client:
            documents = await client.search_keyword("부산", "AT4")

        assert attempts == 2
        assert documents[0].id == "8130788"

    asyncio.run(scenario())


@pytest.mark.parametrize("status_code", [302, 400, 401, 404])
def test_non_retryable_status_fails_without_retry_or_sensitive_details(
    status_code: int,
) -> None:
    async def scenario() -> None:
        attempts = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(status_code, text=f"secret {API_KEY}")

        client, http_client = _client(handler, max_retries=3)
        async with http_client:
            with pytest.raises(KakaoUpstreamError) as caught:
                await client.search_keyword("부산", "AT4")

        assert attempts == 1
        assert API_KEY not in str(caught.value)
        assert "secret" not in str(caught.value)

    asyncio.run(scenario())


def test_retryable_status_exhaustion_raises_safe_upstream_error() -> None:
    async def scenario() -> None:
        attempts = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(503, text=f"secret {API_KEY}")

        client, http_client = _client(handler, max_retries=2)
        async with http_client:
            with pytest.raises(KakaoUpstreamError) as caught:
                await client.search_keyword("부산", "AT4")

        assert attempts == 3
        assert API_KEY not in str(caught.value)
        assert "secret" not in str(caught.value)

    asyncio.run(scenario())


def test_timeout_is_not_retried_and_raises_timeout_error() -> None:
    async def scenario() -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise httpx.ReadTimeout(f"secret {API_KEY}", request=request)

        client, http_client = _client(handler, max_retries=2)
        async with http_client:
            with pytest.raises(UpstreamTimeoutError) as caught:
                await client.search_keyword("부산", "AT4")

        assert attempts == 1
        assert API_KEY not in str(caught.value)
        assert "secret" not in str(caught.value)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "response_factory",
    [
        lambda: httpx.Response(200, content=b"not json"),
        lambda: httpx.Response(200, json={"meta": {}, "documents": "wrong"}),
    ],
)
def test_invalid_response_raises_safe_validation_error(response_factory) -> None:
    async def scenario() -> None:
        client, http_client = _client(lambda _: response_factory())
        async with http_client:
            with pytest.raises(InvalidKakaoResponseError) as caught:
                await client.search_keyword("부산", "AT4")

        assert API_KEY not in str(caught.value)
        assert "not json" not in str(caught.value)

    asyncio.run(scenario())


def test_constructor_rejects_invalid_retry_and_timeout_settings() -> None:
    http_client = httpx.AsyncClient()
    try:
        with pytest.raises(ValueError, match="timeout"):
            KakaoLocalClient(http_client, api_key=API_KEY, timeout=0)
        with pytest.raises(ValueError, match="max_retries"):
            KakaoLocalClient(http_client, api_key=API_KEY, max_retries=-1)
        with pytest.raises(ValueError, match="max_retries"):
            KakaoLocalClient(http_client, api_key=API_KEY, max_retries=4)
        with pytest.raises(ValueError, match="max_retries"):
            KakaoLocalClient(http_client, api_key=API_KEY, max_retries=True)
        with pytest.raises(ValueError, match="retry_delay_seconds"):
            KakaoLocalClient(http_client, api_key=API_KEY, retry_delay_seconds=-1)
    finally:
        asyncio.run(http_client.aclose())


@pytest.mark.parametrize(
    "base_url",
    [
        "http://dapi.kakao.com",
        "https://example.com",
        "https://dapi.kakao.com:444",
        "https://user:password@dapi.kakao.com",
        "https://dapi.kakao.com?target=example.com",
        "https://dapi.kakao.com#fragment",
        "https://dapi.kakao.com/proxy",
        "https://dapi.kakao.com:",
        " https://dapi.kakao.com",
        "not-a-url",
    ],
)
def test_constructor_rejects_noncanonical_kakao_base_url(base_url: str) -> None:
    http_client = httpx.AsyncClient()
    try:
        with pytest.raises(
            ValueError,
            match=r"base_url must be https://dapi\.kakao\.com",
        ) as caught:
            KakaoLocalClient(http_client, api_key=API_KEY, base_url=base_url)

        assert "password" not in str(caught.value)
        assert "target" not in str(caught.value)
    finally:
        asyncio.run(http_client.aclose())


@pytest.mark.parametrize(
    "base_url",
    [
        "https://dapi.kakao.com",
        "https://dapi.kakao.com/",
        "https://dapi.kakao.com:443",
        "https://dapi.kakao.com:443/",
    ],
)
def test_constructor_accepts_only_canonical_kakao_base_urls(base_url: str) -> None:
    http_client = httpx.AsyncClient()
    try:
        KakaoLocalClient(http_client, api_key=API_KEY, base_url=base_url)
    finally:
        asyncio.run(http_client.aclose())


def test_from_settings_uses_application_kakao_configuration(monkeypatch) -> None:
    configured = SimpleNamespace(
        kakao_rest_api_key="configured-key",
        kakao_local_base_url="https://dapi.kakao.com:443",
        kakao_request_timeout_seconds=7.5,
        kakao_max_retries=2,
    )
    monkeypatch.setattr("app.config.settings", configured)

    async def scenario() -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            assert request.url.host == "dapi.kakao.com"
            assert request.headers["Authorization"] == "KakaoAK configured-key"
            if attempts < 3:
                return httpx.Response(503)
            return httpx.Response(200, json=_valid_payload())

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = KakaoLocalClient.from_settings(http_client)
        async with http_client:
            documents = await client.search_keyword("부산", "AT4")

        assert attempts == 3
        assert documents[0].id == "8130788"

    asyncio.run(scenario())
