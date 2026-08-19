# Backend 설계 및 구현 계획

## 1. 목표

사용자의 자연어 여행 질문을 구조화하고, Kakao Local API에서 확인한 실제 장소만 이용해 지도에 바로 표시할 수 있는 여행 계획을 반환한다.

핵심 원칙:

- LLM은 목적지, 기간, 선호도, 장소 검색어와 일정 구성을 담당한다.
- 장소 ID, 공식 장소명, 주소, 좌표, 전화번호, 상세 URL은 Kakao Local API만 신뢰한다.
- LLM이 임의로 생성한 좌표나 후보 목록에 없는 장소 ID는 폐기한다.
- 모든 단계의 결과를 Pydantic으로 검증한다.
- MVP는 DB 없는 단일 요청·응답 구조로 구현한다.

## 2. 기존 코드 재사용

재사용 대상:

- `backend/app/config.py`의 루트 `.env` 로딩
- `backend/app/providers.py`의 Provider registry와 `ProviderResult`
- OpenAI `responses.parse` 구조화 출력
- Gemini `response_json_schema=model_class.model_json_schema()` 처리
- Ollama JSON Schema `format` 처리
- `ConfigDict(extra="forbid")` 기반 검증
- APIRouter, response model, HTTPException 패턴
- TestClient, monkeypatch, fake client 테스트 방식

제외 또는 변경 대상:

- `SupportTicket`, 이미지 분석, TTS, 개념 비교 API는 포함하지 않는다.
- 기존 `TravelPlan.activities`를 실제 `landmarks`, `foods` 모델로 교체한다.
- 클라이언트가 `system_prompt`를 전달하지 못하게 하고 서버 프롬프트를 사용한다.
- 외부 SDK 예외 문자열을 그대로 응답하지 않고 안정적인 오류 코드로 변환한다.

## 3. 목표 구조

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── exceptions.py
│   ├── clients/
│   │   ├── __init__.py
│   │   └── kakao_local_client.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── mock_provider.py
│   │   ├── gemini_provider.py
│   │   ├── openai_provider.py
│   │   └── ollama_provider.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health_router.py
│   │   └── travel_plan_router.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── kakao_local.py
│   │   └── travel_plan.py
│   └── services/
│       ├── __init__.py
│       ├── place_search_service.py
│       └── travel_plan_service.py
└── tests/
    ├── unit/
    │   ├── test_travel_schemas.py
    │   ├── test_kakao_local_client.py
    │   ├── test_place_search_service.py
    │   └── test_provider_contract.py
    └── integration/
        └── test_travel_plan_api.py
```

책임:

- `providers`: Provider별 구조화 출력 차이 처리
- `clients`: Kakao Local HTTP 요청과 원본 응답 파싱
- `services`: 여행 의도, 장소 후보, 일정 결과 조합
- `routers`: HTTP 계약과 상태 코드
- `schemas`: 외부·내부 데이터 경계 검증

## 4. API 계약

### `POST /api/travel-plans/generate`

Swagger 태그: `Travel Planner`

요청:

```json
{
  "message": "부산에 2박 3일 여행을 가고 싶어. 바다와 현지 음식을 좋아해.",
  "provider": "gemini",
  "landmark_count": 6,
  "food_count": 4
}
```

| 필드 | 타입 | 조건 |
|---|---|---|
| `message` | string | 2~1000자 |
| `provider` | string 또는 null | `mock`, `gemini`, `openai`, `ollama`; 생략 시 기본값 |
| `landmark_count` | integer | 기본 6, 1~10 |
| `food_count` | integer | 기본 4, 1~10 |

`system_prompt`는 외부 요청으로 받지 않는다.

응답은 [masterplan.md](masterplan.md)의 공통 API 계약을 따른다. `latency_ms`는 두 LLM 단계와 Kakao 검색을 포함한 전체 처리 시간이다.

### 보조 API

- `GET /health`: 서버 상태와 기본 Provider
- `GET /api/providers`: Provider 설정 여부와 모델명만 반환

API 키, endpoint 인증 헤더, 원본 SDK 설정은 응답하지 않는다.

## 5. Pydantic 모델

모든 외부 요청과 LLM 출력 모델:

```python
model_config = ConfigDict(
    extra="forbid",
    str_strip_whitespace=True,
)
```

주요 모델:

```python
ProviderName = Literal["mock", "gemini", "openai", "ollama"]
PlaceType = Literal["landmark", "food"]


class TravelPlanGenerateRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    provider: ProviderName | None = None
    landmark_count: int = Field(default=6, ge=1, le=10)
    food_count: int = Field(default=4, ge=1, le=10)


class TravelIntent(BaseModel):
    destination: str = Field(min_length=1, max_length=100)
    nights: int = Field(ge=0, le=29)
    days: int = Field(ge=1, le=30)
    preferences: list[str] = Field(default_factory=list, max_length=10)
    landmark_queries: list[str] = Field(min_length=1, max_length=5)
    food_queries: list[str] = Field(min_length=1, max_length=5)


class ItinerarySelection(BaseModel):
    place_id: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=300)
    day: int = Field(ge=1, le=30)
    order: int = Field(ge=1, le=20)


class TravelPlace(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    place_type: PlaceType
    category_name: str = ""
    description: str = Field(min_length=1, max_length=300)
    address: str = ""
    road_address: str = ""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    phone: str = ""
    kakao_place_url: str
    day: int = Field(ge=1, le=30)
    order: int = Field(ge=1, le=20)
```

추가 검증:

- `days == nights + 1`
- 모든 장소의 `day <= days`
- `landmarks`는 `place_type="landmark"`
- `foods`는 `place_type="food"`
- 동일 Kakao 장소 ID 중복 금지
- 최종 배열을 `day`, `order` 순으로 정렬
- LLM이 선택한 `place_id`가 Kakao 후보 ID 집합에 포함되는지 확인

## 6. 처리 파이프라인

### 1단계: 요청 검증

- 메시지 길이, Provider, 요청 장소 개수를 검증한다.
- 선택 Provider와 Kakao REST 설정 여부를 확인한다.

### 2단계: 여행 의도 구조화

LLM에 `TravelIntent`를 요청한다.

예시 결과:

```json
{
  "destination": "부산",
  "nights": 2,
  "days": 3,
  "preferences": ["바다", "해산물", "대중교통"],
  "landmark_queries": ["부산 해변 관광명소", "부산 대표 관광지"],
  "food_queries": ["부산 해산물 맛집", "부산 향토음식"]
}
```

목적지 또는 기간을 확정할 수 없으면 추측하지 않고 `INCOMPLETE_TRAVEL_REQUEST`를 반환한다.

### 3단계: Kakao 장소 후보 검색

- 관광명소 검색어에는 `category_group_code=AT4`를 적용한다.
- 음식점 검색어에는 `category_group_code=FD6`를 적용한다.
- 각 검색 결과를 Kakao 장소 ID 기준으로 합치고 중복 제거한다.
- 목적지 주소와 카테고리 일치 여부로 결과를 필터링한다.
- Provider에 전달할 후보 개수를 내부 상한으로 제한한다.

### 4단계: 후보 기반 일정 구성

LLM에 후보의 `id`, 이름, 카테고리, 주소만 전달한다. LLM은 다음만 반환한다.

- 후보 `place_id`
- 추천 설명
- 일차
- 방문 순서
- 전체 요약

후보에 없는 ID는 폐기한다. 일정 LLM 단계가 실패하면 Kakao 정확도 순 결과를 deterministic하게 일차별 배분하고 `warnings`에 fallback 사실을 남긴다.

### 5단계: 최종 조합과 검증

- Kakao 공식 장소 데이터와 LLM 일정 데이터를 `place_id`로 join한다.
- 요청 개수 이하로 자른다.
- 최종 `TravelPlanContent`를 Pydantic으로 검증한다.
- 일부 장소가 제외돼도 하나 이상 남으면 `200 + warnings`를 반환한다.
- 지도에 표시할 장소가 하나도 없으면 `PLACE_RESOLUTION_FAILED`를 반환한다.

## 7. Kakao Local client

사용 endpoint:

```text
GET https://dapi.kakao.com/v2/local/search/keyword.json
Authorization: KakaoAK {KAKAO_REST_API_KEY}
```

주요 query parameter:

- `query`: 필수 검색어
- `category_group_code`: `AT4` 또는 `FD6`
- `size`: 1~15
- `page`: 필요 시 페이지
- `sort=accuracy`: 좌표 중심이 없을 때 기본값

카테고리 검색 endpoint는 `x`, `y`, `radius` 또는 `rect`가 필요하므로, 부산처럼 넓은 지역의 초기 검색은 지역명이 포함된 키워드 검색을 기본으로 한다.

원본 응답 변환:

```text
id                → id
place_name        → name
category_name     → category_name
address_name      → address
road_address_name → road_address
y                 → latitude
x                 → longitude
phone             → phone
place_url         → kakao_place_url
```

`x`, `y`는 문자열이므로 float로 변환한다. `x`는 경도, `y`는 위도다.

HTTP 정책:

- 공통 `httpx.Client` 또는 lifespan client 재사용
- connect/read timeout 설정
- 429와 일시적 5xx만 제한적으로 재시도
- 400/401은 재시도하지 않음
- 응답 상태와 JSON 구조를 검증
- REST API 키와 Authorization header를 로그에 남기지 않음

## 8. Provider 구현

모든 Provider는 두 구조화 모델을 동일하게 생성할 수 있어야 한다.

- `TravelIntent`
- `GroundedItinerary` 또는 동일 역할의 일정 모델

Provider 규칙:

- Mock: 고정된 부산 후보와 일정으로 개발·테스트
- Gemini: `response_json_schema=model_class.model_json_schema()` 사용
- OpenAI: `responses.parse(..., text_format=model_class)` 사용
- Ollama: `format=model_class.model_json_schema()` 사용

프롬프트에는 다음 제약을 포함한다.

- 장소 후보에 없는 ID를 만들지 않는다.
- 좌표, 주소, URL을 생성하지 않는다.
- 박·일과 장소 일차 범위를 맞춘다.
- 출력 Schema 이외의 필드를 추가하지 않는다.

## 9. 환경 변수

루트 `.env.example`:

```dotenv
LLM_PROVIDER=mock

OPENAI_API_KEY=
OPENAI_MODEL=
GEMINI_API_KEY=
GEMINI_MODEL=
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2

KAKAO_REST_API_KEY=
KAKAO_LOCAL_BASE_URL=https://dapi.kakao.com
KAKAO_REQUEST_TIMEOUT_SECONDS=5
KAKAO_SEARCH_SIZE=10
KAKAO_MAX_RETRIES=1

REQUEST_TIMEOUT_SECONDS=60
```

`KAKAO_JAVASCRIPT_KEY`는 프런트 설정이며 백엔드에서 사용하지 않는다.

## 10. 오류 계약

권장 오류 body:

```json
{
  "detail": {
    "code": "KAKAO_UPSTREAM_ERROR",
    "message": "장소 정보를 가져오지 못했습니다.",
    "request_id": "..."
  }
}
```

| HTTP | 코드 | 상황 |
|---|---|---|
| 422 | `INVALID_REQUEST` | 입력 길이, Provider, 개수 범위 오류 |
| 422 | `INCOMPLETE_TRAVEL_REQUEST` | 목적지 또는 기간을 확정할 수 없음 |
| 503 | `PROVIDER_NOT_CONFIGURED` | Provider 키 또는 모델 미설정 |
| 503 | `KAKAO_NOT_CONFIGURED` | Kakao REST 키 미설정 |
| 502 | `LLM_UPSTREAM_ERROR` | LLM 호출 또는 구조화 출력 실패 |
| 502 | `KAKAO_UPSTREAM_ERROR` | Kakao 인증·응답 오류 |
| 504 | `UPSTREAM_TIMEOUT` | 외부 API timeout |
| 502 | `PLACE_RESOLUTION_FAILED` | 지도에 표시할 장소가 하나도 없음 |

원본 SDK 예외, API 키, 외부 response body 전체를 클라이언트에 반환하지 않는다.

## 11. 보안과 운영

- 실제 `.env`와 API 키를 Git에 커밋하지 않는다.
- Kakao REST 키는 백엔드에만 두고 프런트 응답에 포함하지 않는다.
- Kakao API host는 설정된 고정 base URL만 사용한다.
- 사용자 메시지는 1000자, 장소 요청은 종류별 10개로 제한한다.
- system prompt와 외부 API query 구조를 사용자 입력으로 받지 않는다.
- 운영 로그에는 API 키와 전체 사용자 질문을 기록하지 않는다.
- 사용자에게 반환하는 설명과 장소명은 프런트에서 HTML escape한다.
- 운영 환경에서는 요청 횟수 제한과 장소 검색 캐시를 추가한다.
- Streamlit이 서버에서 FastAPI를 호출하는 MVP에는 브라우저 CORS가 필요 없다. 향후 React가 직접 호출할 때만 허용 origin을 제한해 추가한다.

## 12. 테스트 계획

### Schema와 서비스

- `2박 3일`이 `nights=2`, `days=3`으로 검증된다.
- `days != nights + 1`을 거부한다.
- 장소 `day`가 여행 일수를 넘으면 거부한다.
- 추가 필드와 후보 밖 `place_id`를 거부한다.
- 동일 장소 ID가 중복 제거된다.
- 결과가 `day`, `order` 순으로 정렬된다.

### Provider

- 모든 Provider가 같은 `TravelIntent`, 일정 계약을 반환한다.
- Gemini가 `response_schema`가 아니라 `response_json_schema`를 사용한다.
- 일정 생성 실패 시 deterministic fallback이 동작한다.

### Kakao client

- `Authorization: KakaoAK ...` 헤더가 포함된다.
- 관광명소는 `AT4`, 음식점은 `FD6`로 요청한다.
- `x → longitude`, `y → latitude`가 정확하다.
- 빈 결과, 400, 401, 429, 5xx, timeout을 구분한다.
- REST API 키가 오류 문자열과 로그에 포함되지 않는다.

### API 통합

- 정상 Mock 요청이 공통 응답 계약을 반환한다.
- 일부 장소 실패는 `200 + warnings`다.
- 전체 장소 실패는 `PLACE_RESOLUTION_FAILED`다.
- `/api/providers`에 키가 노출되지 않는다.
- Swagger에 `/api/travel-plans/generate`가 노출된다.

기본 테스트는 fake Provider와 `httpx.MockTransport`를 사용한다. 실제 Gemini와 Kakao 호출은 별도 integration marker로 분리해 기본 CI에서 실행하지 않는다.

## 13. 구현 순서

1. 현재 백엔드에서 필요한 파일만 새 프로젝트로 복사한다.
2. 여행 요청, 의도, Kakao 후보, 일정, 최종 응답 Schema를 만든다.
3. deterministic Mock Provider로 Swagger 계약을 완성한다.
4. Kakao Local client와 장소 후보 검색·중복 제거를 구현한다.
5. 후보 기반 일정 구성과 fallback을 구현한다.
6. Gemini, OpenAI, Ollama 구조화 Provider를 연결한다.
7. 표준 오류, timeout, warnings를 구현한다.
8. 단위·통합 테스트와 실제 API smoke test를 분리한다.

## 14. 공식 참고 자료

- [Kakao Local REST API](https://developers.kakao.com/docs/ko/local/dev-guide)
- [Kakao REST API 시작하기](https://developers.kakao.com/docs/ko/rest-api/getting-started)
- [Kakao 보안 권장 사항](https://developers.kakao.com/docs/ko/getting-started/security-guideline)
