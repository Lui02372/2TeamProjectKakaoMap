# 여행 지도 서비스 설계

## 목표

로그인한 사용자가 텍스트 또는 음성으로 여행을 요청하면, 여행 의도와 음식 취향을 반영한 2박 3일 일정, 검증된 랜드마크와 음식점, Kakao 지도 마커 및 장소 상세 링크를 받는다. 사용자는 결과와 개별 장소를 즐겨찾기로 저장하고 이전 여행을 다시 열 수 있다.

## 범위와 기술 선택

- 화면: 기존 Streamlit 앱을 여행 서비스 중심 화면으로 재구성한다.
- API: FastAPI가 인증 검증, 여행 생성, 장소 검증, 음성 처리와 SSE를 제공한다.
- 인증 및 영속화: Supabase Cloud Auth(email/password)와 Postgres를 사용한다.
- 권한: Supabase JWT를 API 요청의 `Authorization: Bearer` 헤더로 전달한다. 모든 공개 테이블에 RLS를 적용한다.
- 장소: Kakao Local REST API의 검증된 장소 ID, 좌표, 장소 URL만 지도에 표시한다.
- LLM: Ollama를 기본 제공자로 사용하고 Gemini/OpenAI는 키가 있을 때만 선택 제공자로 활성화한다.
- 음성: STT는 `faster-whisper`, TTS는 `piper-tts`를 기본으로 하여 유료 음성 API 의존을 제거한다.
- 상태: Redis(Docker)는 생성 작업 상태와 짧은 TTL의 장소/LLM 결과 캐시에 사용한다. 영구 사용자 데이터는 Supabase에만 저장한다.
- 실시간 진행: FastAPI SSE가 `received`, `interpreting`, `searching_places`, `planning`, `complete`, `failed` 이벤트를 전달한다.

## 사용자 흐름

1. 사용자는 회원가입 또는 로그인한다.
2. 홈 화면에서 여행 문장을 입력하거나 마이크로 녹음한다.
3. 프런트엔드는 음성 파일을 STT API에 전송해 텍스트 입력란에 전사 결과를 넣는다.
4. 사용자가 여행 생성 버튼을 누르면 SSE 연결을 열고 진행 상태를 표시한다.
5. 백엔드는 사용자 JWT를 검증하고, 여행 의도(지역, 숙박일, 관심사, 음식 취향)를 구조화한다.
6. 지역·관심사·음식 취향으로 Kakao Local 후보를 검색해 실제 장소 데이터만 수집한다.
7. LLM은 후보 집합 안에서 일정을 구성한다. 후보 밖의 장소 ID나 좌표는 응답에 포함할 수 없다.
8. 생성 결과는 `trips`, `trip_places`에 저장되고, 화면은 일정 탭·지도 탭·즐겨찾기 탭에 렌더링한다.
9. 사용자는 장소 또는 전체 여행을 즐겨찾기에 저장하고, 저장한 여행을 다시 조회한다.

## 화면 구조

- `로그인`: 이메일·비밀번호 회원가입, 로그인, 로그아웃, 현재 로그인 상태.
- `여행 만들기`: 큰 텍스트 입력, 녹음/전사 버튼, 숙박일과 관심사 칩, 생성 버튼, SSE 진행 상태.
- `일정`: 일차별 랜드마크·음식점 카드와 TTS 재생 버튼.
- `Kakao 지도`: 장소 유형·일차 필터, 색상별 마커, 카드, Kakao 장소 상세 링크.
- `내 여행`: 저장된 요청과 여행 기록을 재열람.
- `즐겨찾기`: 사용자가 저장한 장소와 여행 목록.

## API 계약

- `POST /api/auth/session/verify`: Authorization JWT를 검증해 현재 사용자를 반환한다.
- `POST /api/voice/transcribe`: 오디오 업로드를 한국어 텍스트로 전사한다.
- `POST /api/voice/synthesize`: 여행 요약을 로컬 음성 파일로 생성한다.
- `POST /api/travel-plans`: 여행 요청을 만들고 `request_id`를 반환한다.
- `GET /api/travel-plans/{request_id}/events`: SSE 진행 이벤트를 반환한다.
- `GET /api/travel-plans/{request_id}`: 완료된 여행 계획을 반환한다.
- `POST /api/favorites/places`, `DELETE /api/favorites/places/{id}`: 장소 즐겨찾기를 관리한다.
- `GET /api/favorites`: 로그인 사용자의 즐겨찾기를 반환한다.

## 데이터 모델

```text
auth.users
  └─ public.profiles (user_id PK/FK, display_name, created_at)
       ├─ travel_requests (id PK, user_id FK, query, input_source, status, created_at)
       ├─ trips (id PK, user_id FK, request_id FK, destination, nights, days, summary, created_at)
       │    └─ trip_places (id PK, trip_id FK, kakao_place_id, place_type, name, day_number,
       │                      display_order, latitude, longitude, kakao_place_url, snapshot JSONB)
       └─ favorite_places (id PK, user_id FK, kakao_place_id, place_snapshot JSONB, created_at)
```

각 `user_id` 소유 테이블은 SELECT/INSERT/UPDATE/DELETE 정책에서 `(select auth.uid()) = user_id`를 사용한다. `trip_places`는 상위 `trips.user_id` 소유 여부를 확인하는 정책을 사용한다. service-role 키는 서버에서만 사용하며 프런트에 노출하지 않는다.

## 환경 변수

```dotenv
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_AUDIENCE=authenticated
REDIS_URL=redis://127.0.0.1:6379/0
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
KAKAO_REST_API_KEY=
KAKAO_JAVASCRIPT_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=
OPENAI_API_KEY=
OPENAI_MODEL=
```

`SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `KAKAO_REST_API_KEY`는 백엔드 전용이다. 프런트는 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `KAKAO_JAVASCRIPT_KEY`만 읽을 수 있다.

## 오류 및 운영 원칙

- 키나 로컬 서비스가 없으면 해당 제공자를 선택 불가로 표시하고 mock 또는 설정된 제공자로 대체한다.
- SSE 연결이 끊겨도 `GET /api/travel-plans/{request_id}`로 완료 결과를 복구할 수 있다.
- 외부 장소 검색 실패는 사용자에게 재시도 안내를 주며 가공된 장소를 저장하지 않는다.
- 음성 파일 크기·MIME 타입·길이를 제한하며 요청 단위 임시 파일은 처리 뒤 제거한다.
- Redis는 캐시/진행 상태만 보관하고 장애 시 DB 기반 결과 조회는 계속 가능해야 한다.

## 검증 기준

- 회원 A가 회원 B의 요청·여행·즐겨찾기를 조회하거나 수정할 수 없다.
- 부산 2박 3일·음식 취향 요청이 랜드마크와 음식점, Kakao URL·좌표를 포함한 일정으로 완료된다.
- 텍스트와 음성 입력 모두 같은 여행 생성 파이프라인을 사용한다.
- 이벤트 순서와 실패 이벤트가 SSE에서 일관되게 전달된다.
- 지도에는 Kakao에서 확인한 URL과 유효 좌표가 있는 장소만 표시된다.
