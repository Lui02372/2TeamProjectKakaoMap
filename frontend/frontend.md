# Frontend 구현 계획

## 1. 목표

Streamlit 화면에서 여행 질문을 입력하고, 백엔드가 반환한 여행 요약·관광명소·음식점을 카드와 카카오 지도에 함께 표시한다.

프런트엔드는 다음 책임만 가진다.

- 사용자 입력과 Provider 선택
- 백엔드 API 호출
- 응답 계약 검증과 화면 상태 관리
- 여행 요약과 장소 카드 렌더링
- Kakao Maps JavaScript SDK를 이용한 지도 렌더링

LLM과 Kakao Local REST API는 프런트에서 직접 호출하지 않는다.

## 2. 기존 코드 재사용

| 기존 파일 | 재사용 내용 | 변경 방향 |
|---|---|---|
| `frontend/app.py` | Streamlit 설정과 페이지 구조 | 여행 플래너와 환경 상태 두 페이지로 단순화 |
| `frontend/core/api_client.py` | Backend URL, timeout, HTTP 오류 처리 | 상태 코드와 응답 계약 오류를 구분 |
| `frontend/clients/agent_client.py` | 얇은 API client 함수 패턴 | 여행 전용 `travel_client.py` 추가 |
| `frontend/app_pages/09_structured_output.py` | form → API → 결과 처리 패턴 | JSON 출력 대신 요약·카드·지도 출력 |
| `frontend/app_pages/02_environment.py` | 백엔드 상태 확인 | 개발용 페이지로 유지 |

## 3. 목표 구조

```text
frontend/
├── app.py
├── app_pages/
│   ├── 01_travel_planner.py
│   └── 02_environment.py
├── clients/
│   ├── __init__.py
│   └── travel_client.py
├── components/
│   ├── __init__.py
│   ├── kakao_map.py
│   ├── place_cards.py
│   └── trip_summary.py
├── core/
│   ├── __init__.py
│   ├── api_client.py
│   └── config.py
├── models/
│   ├── __init__.py
│   └── travel.py
└── tests/
    ├── test_travel_client.py
    ├── test_travel_models.py
    ├── test_kakao_map.py
    └── test_place_view.py
```

백엔드 Python 모델을 직접 import하지 않는다. `models/travel.py`에 화면이 소비하는 응답 DTO를 별도로 정의해 두 실행 환경의 결합을 피한다.

## 4. 화면 구성

### 요청 영역

`st.form`을 사용하여 위젯 변경 때마다 API가 재호출되지 않게 한다.

- 여행 질문 `st.text_area`
- Provider 선택 `st.selectbox`
- 관광명소 개수 `st.number_input` 또는 `st.slider`
- 음식점 개수 `st.number_input` 또는 `st.slider`
- `여행 계획 만들기` 제출 버튼

초기 예시:

> 부산에 2박 3일 여행을 가고 싶어요. 대중교통을 이용하고 해산물을 좋아해요.

개발 기본 Provider는 `mock`으로 둔다.

### 결과 요약

- 목적지
- `2박 3일`
- 여행 요약
- Provider와 모델
- 전체 처리 시간
- 부분 성공 `warnings`

### 결과 본문

넓은 화면에서는 `st.columns([3, 2])`를 사용한다.

- 왼쪽: 카카오 지도
- 오른쪽: 장소 카드

그 위에 `전체`, `1일차`, `2일차`, `3일차` 필터를 둔다. 필터 변경 시 카드와 지도에 동일한 장소 목록을 전달한다.

장소 카드는 다음 정보를 표시한다.

- 일차와 방문 순서
- 장소명과 `landmark` 또는 `food`
- 추천 설명
- 도로명 주소 우선, 없으면 지번 주소
- 전화번호
- 카카오맵 상세보기 링크

## 5. API client

`clients/travel_client.py`:

```python
def generate_travel_plan(
    message: str,
    provider: str,
    landmark_count: int,
    food_count: int,
) -> dict:
    return request(
        "POST",
        "/api/travel-plans/generate",
        json={
            "message": message,
            "provider": provider,
            "landmark_count": landmark_count,
            "food_count": food_count,
        },
    )
```

상세 요청·응답 계약은 [masterplan.md](masterplan.md)의 공통 API 계약을 따른다.

프런트 응답 모델은 최소한 다음을 검증한다.

- `days == nights + 1`
- `landmarks[].place_type == "landmark"`
- `foods[].place_type == "food"`
- 위도 `-90~90`, 경도 `-180~180`
- `day <= content.days`
- 동일 장소 ID 중복 없음

## 6. 상태 관리

권장 `st.session_state`:

```text
travel_plan_response   마지막 성공 응답
travel_plan_error      마지막 오류
selected_day           전체 또는 선택한 일차
selected_place_type    all, landmark, food
last_request           마지막 제출 입력
```

처리 흐름:

```text
form 제출
  → travel_client.generate_travel_plan()
  → 응답 Pydantic 검증
  → travel_plan_response 저장
  → 일차·장소 종류 필터
  → 요약, 카드, 지도 렌더링
```

새 요청이 실패하더라도 마지막 성공 결과를 바로 지우지 않는다. 오류를 표시하고 사용자가 다시 시도하거나 이전 결과를 볼 수 있게 한다.

## 7. 카카오 지도 컴포넌트

`components/kakao_map.py`의 공개 함수:

```python
def build_kakao_map_html(places: list[PlaceView], javascript_key: str) -> str:
    ...


def render_kakao_map(places: list[PlaceView], javascript_key: str) -> None:
    ...
```

`build_kakao_map_html`은 순수 함수로 만들어 단위 테스트가 가능하게 한다. `render_kakao_map`은 `streamlit.components.v1.html`만 담당한다.

SDK 로딩:

```html
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=KAKAO_JAVASCRIPT_KEY&autoload=false"></script>
```

이후 `kakao.maps.load(callback)` 안에서 지도를 생성한다. 장소 검색은 백엔드가 담당하므로 `libraries=services`는 사용하지 않는다.

지도 동작:

- 유효 좌표 전체로 `LatLngBounds`를 만든다.
- 한 장소만 있으면 해당 장소를 중심으로 적당한 level을 적용한다.
- 관광명소와 음식점의 마커 색상 또는 아이콘을 구분한다.
- 마커 클릭 시 장소명, 설명, 주소, 상세 링크를 정보창에 표시한다.
- 선택한 일차와 장소 종류에 맞는 마커만 다시 그린다.
- 좌표가 없거나 범위를 벗어난 장소는 제외하고 경고를 남긴다.
- 표시할 장소가 없으면 빈 지도 대신 안내 문구를 보여준다.

좌표 순서:

```javascript
new kakao.maps.LatLng(place.latitude, place.longitude)
```

Kakao Local 원본은 `x=longitude`, `y=latitude`이므로 백엔드에서 이름을 바꾸고 float로 변환한 결과만 사용한다.

## 8. HTML과 JavaScript 안전성

- 사용자 입력이나 LLM 문자열을 JavaScript 코드에 직접 문자열 보간하지 않는다.
- 장소 데이터를 `json.dumps(..., ensure_ascii=False)`로 직렬화한다.
- `</script>` 종료 문자열과 HTML 특수문자를 안전하게 escape하거나 Base64 JSON으로 전달한다.
- 정보창 HTML은 별도 escape 함수를 거친 텍스트만 사용한다.
- 외부 링크는 `https://place.map.kakao.com` 또는 허용된 Kakao URL인지 검증한다.

Streamlit의 `components.html`은 iframe에서 실행되므로 양방향 이벤트 연동은 MVP에서 제외한다. 마커 클릭은 iframe 안의 정보창까지만 처리하고, Streamlit 필터는 Python 위젯으로 제어한다.

## 9. 키와 설정

루트 `.env.example`:

```dotenv
BACKEND_API_URL=http://127.0.0.1:8000
KAKAO_JAVASCRIPT_KEY=
```

- JavaScript 키는 지도 HTML에서 보이는 클라이언트 키다.
- `KAKAO_REST_API_KEY`를 프런트 코드, HTML, API 응답에 넣지 않는다.
- 카카오 개발자 콘솔의 JavaScript SDK 도메인에 개발·운영 origin을 등록한다.
- Streamlit 기본 개발 origin은 `http://localhost:8501`이다.
- `127.0.0.1`을 사용할 경우 그 origin도 실제 환경에서 확인한다.
- Streamlit iframe에 대한 카카오 공식 전용 가이드는 없으므로 개발·운영 환경에서 smoke test한다.

## 10. 로딩과 오류 상태

| 상황 | 화면 동작 |
|---|---|
| 최초 진입 | 여행 요청을 입력하라는 안내 표시 |
| 요청 중 | `st.spinner`로 LLM·장소 검색 중임을 표시 |
| 422 | 목적지·기간·입력 범위를 수정하도록 안내 |
| 502 | Provider 또는 Kakao 외부 API 오류로 구분해 표시 |
| 503 | 필요한 Provider/Kakao 설정이 없음을 표시 |
| 504 | 외부 API timeout과 재시도 안내 |
| 응답 계약 오류 | 백엔드 응답 형식 오류로 표시하고 원본 JSON은 숨김 |
| 일부 장소 실패 | `warnings`를 표시하고 정상 장소는 계속 렌더링 |
| JavaScript 키 누락 | 카드와 링크는 표시하고 지도만 비활성화 |
| 지도 SDK 실패 | 카드와 카카오맵 상세 링크를 fallback으로 유지 |

## 11. 구현 순서

1. 기존 `app.py`, `core/api_client.py`를 복사하고 페이지를 단순화한다.
2. `models/travel.py`와 `travel_client.py`를 만든다.
3. Mock 응답으로 여행 요약과 장소 카드를 구현한다.
4. `build_kakao_map_html`과 지도 마커를 구현한다.
5. 일차·장소 종류 필터를 지도와 카드에 함께 연결한다.
6. 로딩, 오류, warnings, 빈 결과를 처리한다.
7. HTML 안전 직렬화와 키 누락 처리를 테스트한다.
8. 실제 카카오 개발 도메인과 운영 도메인에서 smoke test한다.

## 12. 테스트 계획

### 단위 테스트

- API client가 정확한 경로와 payload를 전달한다.
- 응답 모델이 잘못된 박·일, 장소 유형, 좌표를 거부한다.
- 장소 목록이 `day`, `order` 순으로 정렬된다.
- 전체·일차·장소 종류 필터가 올바르게 동작한다.
- 지도 HTML에 올바른 좌표와 마커 데이터가 들어간다.
- 장소명에 `</script>` 또는 HTML이 있어도 실행되지 않는다.
- JavaScript 키가 없으면 지도 렌더링을 중단한다.

### 통합 테스트

- Mock 백엔드 응답으로 요약·카드·지도를 생성한다.
- 422, 502, 503, 504와 timeout을 구분한다.
- 일부 장소 실패 시 `warnings`와 정상 장소를 함께 보여준다.
- 다음 요청 실패 후에도 이전 성공 결과가 유지된다.

### 수동 인수 테스트

- “부산에 2박 3일 여행” 요청이 성공한다.
- 관광명소와 음식점 카드가 구분되어 표시된다.
- 모든 장소 마커가 실제 좌표에 표시된다.
- 일차 필터가 카드와 지도에 동시에 적용된다.
- 마커 또는 카드에서 카카오맵 상세 페이지를 열 수 있다.
- 지도 SDK가 실패해도 장소 정보는 사용할 수 있다.

## 13. 공식 참고 자료

- [Kakao 지도 Web API 가이드](https://apis.map.kakao.com/web/guide/)
- [Kakao 지도 Web API 문서](https://apis.map.kakao.com/web/documentation/)
- [Kakao 앱 키 설정](https://developers.kakao.com/docs/ko/app-setting/app)
