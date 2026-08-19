# Travel Service MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a secure, logged-in travel planner that accepts text or 음성(voice), generates verified Kakao places, streams progress, displays a Kakao map, and persists user trips and favorites.

**Architecture:** Keep Streamlit as the user interface and FastAPI as the trusted application API. Streamlit authenticates through Supabase Auth and attaches the user's JWT to API calls; FastAPI verifies that token with Supabase and performs data work under the user context. Redis is only a short-lived event/cache store, while Supabase Postgres is the system of record.

**Tech Stack:** Python 3.14, Streamlit, FastAPI, Supabase Cloud/Auth/Postgres, Redis 7 Docker image, `redis`, `supabase`, `sse-starlette`, `faster-whisper`, `piper-tts`, Ollama, Gemini/OpenAI optional, Kakao Local and Maps APIs.

## Global Constraints

- Use Supabase email/password Auth with a user JWT on every protected API request.
- Enable RLS on every public Supabase table; users may access only rows they own.
- Never expose `SUPABASE_SERVICE_ROLE_KEY`, LLM keys, or `KAKAO_REST_API_KEY` to Streamlit/browser code.
- Accept only Kakao Local verified IDs, coordinates, and `https://place.map.kakao.com/...` URLs for map markers.
- Redis is cache/event state only. A persisted trip must remain readable if Redis is unavailable.
- Use local `faster-whisper` and `piper-tts` by default; OpenAI audio is opt-in only.
- Do not claim Gemini grounding is free; show it as optional paid-tier functionality.
- The repository currently has no Git metadata, so omit commits until it is initialized as a repository.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `.env.example` | Complete non-secret environment-variable template and comments. |
| `requirements.txt` | Runtime and test dependencies. |
| `docker-compose.yml` | Redis development service with a persistent named volume. |
| `supabase/migrations/0001_travel_service.sql` | Tables, indexes, trigger, RLS, and policies. |
| `backend/app/config.py` | Typed validation for every backend setting. |
| `backend/app/auth.py` | Bearer-token validation and `CurrentUser` dependency. |
| `backend/app/repositories/travel_repository.py` | User-scoped Supabase persistence. |
| `backend/app/services/travel_plan_service.py` | Intent parsing, Kakao candidate lookup, provider generation, and persistence. |
| `backend/app/services/generation_events.py` | Redis event publisher/subscriber with TTL. |
| `backend/app/routers/travel_router.py` | Protected travel creation, result, favorites, and SSE routes. |
| `backend/app/services/voice_service.py` | Local STT/TTS adapters and input validation. |
| `backend/app/routers/voice_router.py` | Protected transcription and speech routes. |
| `frontend/core/supabase_auth.py` | Sign-up, login, logout, and Streamlit-session token management. |
| `frontend/core/authenticated_api.py` | JWT-authenticated FastAPI request/SSE helpers. |
| `frontend/app_pages/00_login.py` | Login and registration view. |
| `frontend/app_pages/12_travel_kakaomap.py` | Travel composer, live progress, result tabs, map, and favorites. |
| `frontend/components/voice_input.py` | Browser/Streamlit audio upload and transcription UI. |
| `frontend/components/travel_results.py` | Itinerary, map-filter, and favorite controls. |

## Task 1: Configuration, dependencies, and Redis development runtime

**Files:**
- Modify: `.env.example`, `.gitignore`, `requirements.txt`, `backend/app/config.py`
- Create: `docker-compose.yml`, `backend/tests/unit/test_config.py`

**Interfaces:**
- Produces `Settings.supabase_url`, `Settings.supabase_publishable_key`, `Settings.supabase_service_role_key`, `Settings.redis_url`, `Settings.voice_max_upload_mb`, and `Settings.ollama_model`.
- Produces `docker compose up -d redis` on `redis://127.0.0.1:6379/0`.

- [ ] **Step 1: Write configuration tests.**

```python
def test_settings_reads_service_values(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    settings = Settings()
    assert settings.supabase_url == "https://project.supabase.co"
    assert settings.redis_url.endswith("/0")

def test_settings_rejects_non_positive_voice_limit(monkeypatch):
    monkeypatch.setenv("VOICE_MAX_UPLOAD_MB", "0")
    with pytest.raises(ValueError, match="VOICE_MAX_UPLOAD_MB"):
        Settings()
```

- [ ] **Step 2: Run the configuration tests and verify they fail.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_config.py -q`
Expected: FAIL because Supabase and voice settings do not exist.

- [ ] **Step 3: Add the required runtime configuration.**

Add these `.env.example` keys without real values:

```dotenv
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_AUDIENCE=authenticated
REDIS_URL=redis://127.0.0.1:6379/0
VOICE_MAX_UPLOAD_MB=10
WHISPER_MODEL=base
PIPER_VOICE=ko_KR-kss-medium
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
KAKAO_REST_API_KEY=
KAKAO_JAVASCRIPT_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=
OPENAI_API_KEY=
OPENAI_MODEL=
```

Add `redis>=5`, `supabase>=2`, `sse-starlette>=2`, `faster-whisper>=1`, `piper-tts>=1`, and `pytest-asyncio>=0.24` to `requirements.txt`. Add `.env` local values only for non-secret defaults; leave cloud keys blank until supplied by the user. Create this Redis service:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: ["redis-server", "--appendonly", "yes"]
    volumes: ["redis-data:/data"]
volumes:
  redis-data:
```

- [ ] **Step 4: Run configuration tests and dependency/Redis checks.**

Run: `..\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt; docker compose up -d redis; docker compose exec redis redis-cli ping`
Expected: tests pass and Redis returns `PONG`.

## Task 2: Supabase schema and row-level access policy

**Files:**
- Create: `supabase/migrations/0001_travel_service.sql`, `backend/tests/integration/test_travel_schema_contract.py`

**Interfaces:**
- `profiles.user_id`, `travel_requests.user_id`, `trips.user_id`, and `favorite_places.user_id` reference `auth.users(id)`.
- `trip_places.trip_id` references `trips(id)`.
- Every user-owned table uses `(select auth.uid()) = user_id` for RLS.

- [ ] **Step 1: Write SQL-contract tests.**

```python
def test_migration_enables_rls_for_all_user_tables():
    migration = Path("../supabase/migrations/0001_travel_service.sql").read_text()
    for table in ("profiles", "travel_requests", "trips", "trip_places", "favorite_places"):
        assert f"alter table public.{table} enable row level security" in migration.lower()

def test_migration_uses_auth_uid_for_ownership():
    migration = Path("../supabase/migrations/0001_travel_service.sql").read_text()
    assert "(select auth.uid()) = user_id" in migration
```

- [ ] **Step 2: Run the contract tests and verify they fail.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_travel_schema_contract.py -q`
Expected: FAIL because the migration does not exist.

- [ ] **Step 3: Create the migration.**

The migration must create UUID primary keys, owner indexes, `updated_at` trigger for `profiles`, a unique `(user_id, kakao_place_id)` constraint on `favorite_places`, and policies for own-row read/write. `trip_places` policies must use an `exists` subquery against `trips` rather than trusting a client-supplied user ID.

```sql
create policy "users read own trips" on public.trips
for select to authenticated using ((select auth.uid()) = user_id);

create policy "users read own trip places" on public.trip_places
for select to authenticated using (
  exists (select 1 from public.trips t where t.id = trip_id and t.user_id = (select auth.uid()))
);
```

- [ ] **Step 4: Run tests and apply the SQL to the Supabase Cloud SQL editor.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_travel_schema_contract.py -q`
Expected: PASS. Apply only after the user supplies the target Supabase project credentials.

## Task 3: JWT authentication and user-scoped persistence

**Files:**
- Create: `backend/app/auth.py`, `backend/app/repositories/__init__.py`, `backend/app/repositories/travel_repository.py`, `backend/tests/unit/test_auth.py`, `backend/tests/unit/test_travel_repository.py`
- Modify: `backend/app/main.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str

async def require_current_user(authorization: Annotated[str, Header()]) -> CurrentUser: ...

class TravelRepository:
    async def create_request(self, user: CurrentUser, query: str, input_source: str) -> UUID: ...
    async def save_trip(self, user: CurrentUser, request_id: UUID, plan: TravelPlanResult) -> UUID: ...
    async def get_trip(self, user: CurrentUser, trip_id: UUID) -> TravelPlanResult | None: ...
    async def toggle_favorite(self, user: CurrentUser, place: TravelPlace) -> bool: ...
```

- [ ] **Step 1: Write failing auth and repository tests.**

```python
@pytest.mark.asyncio
async def test_require_current_user_rejects_missing_bearer_token():
    with pytest.raises(HTTPException) as error:
        await require_current_user("")
    assert error.value.status_code == 401

@pytest.mark.asyncio
async def test_repository_binds_each_query_to_user_token(fake_supabase):
    repository = TravelRepository(fake_supabase)
    await repository.create_request(CurrentUser(UUID(int=1), "a@example.com"), "부산", "text")
    assert fake_supabase.last_insert["user_id"] == str(UUID(int=1))
```

- [ ] **Step 2: Run the unit tests and verify they fail.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_auth.py tests/unit/test_travel_repository.py -q`
Expected: FAIL because auth and repository modules do not exist.

- [ ] **Step 3: Implement bearer-token validation and repository boundaries.**

Validate the `Bearer` header through Supabase Auth `get_user(token)`. Return a stable 401 envelope for missing, malformed, expired, or invalid sessions. Repositories must use the request user's JWT so Supabase RLS remains effective; do not use `SUPABASE_SERVICE_ROLE_KEY` for ordinary user data.

- [ ] **Step 4: Add the auth dependency to protected router endpoints and run tests.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_auth.py tests/unit/test_travel_repository.py -q`
Expected: PASS.

## Task 4: Verified travel generation and SSE lifecycle

**Files:**
- Create: `backend/app/services/generation_events.py`, `backend/app/services/travel_plan_service.py`, `backend/app/routers/travel_router.py`, `backend/tests/unit/test_generation_events.py`, `backend/tests/integration/test_travel_router.py`
- Modify: `backend/app/main.py`, `backend/app/schemas_food.py`

**Interfaces:**

```python
class GenerationStage(StrEnum):
    RECEIVED = "received"; INTERPRETING = "interpreting"; SEARCHING_PLACES = "searching_places"
    PLANNING = "planning"; COMPLETE = "complete"; FAILED = "failed"

async def create_travel_plan(payload: TravelRequest, user: CurrentUser) -> TravelJob: ...
async def event_stream(request_id: UUID, user: CurrentUser) -> AsyncIterator[ServerSentEvent]: ...
```

- [ ] **Step 1: Write failing generation tests.**

```python
@pytest.mark.asyncio
async def test_service_publishes_ordered_stages_and_never_accepts_unverified_places():
    result = await service.generate(request, user)
    assert events.stages == ["received", "interpreting", "searching_places", "planning", "complete"]
    assert {place.id for place in result.places} <= kakao_client.returned_ids

def test_events_endpoint_rejects_other_users(client, other_user_token):
    response = client.get(f"/api/travel-plans/{request_id}/events", headers=auth(other_user_token))
    assert response.status_code == 404
```

- [ ] **Step 2: Run targeted tests and verify they fail.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_generation_events.py tests/integration/test_travel_router.py -q`
Expected: FAIL because the travel job APIs do not exist.

- [ ] **Step 3: Implement the job contract and routes.**

Create `POST /api/travel-plans` returning `{request_id, status}`, `GET /api/travel-plans/{request_id}/events`, `GET /api/travel-plans/{request_id}`, and favorite routes. Store generation event JSON under `travel:events:{request_id}` with a 30-minute TTL. Persist `travel_requests` before generation and `trips`/`trip_places` after success. Parse destination, nights, interests, and food preferences; call Kakao first; give only verified candidates to the configured provider; validate every selected place against candidate IDs and URLs.

- [ ] **Step 4: Verify completed, failed, and Redis-unavailable paths.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_generation_events.py tests/integration/test_travel_router.py -q`
Expected: PASS; a Redis outage yields a clear 503 during event setup while existing persisted trips remain retrievable.

## Task 5: Local voice input and output APIs

**Files:**
- Create: `backend/app/services/voice_service.py`, `backend/app/routers/voice_router.py`, `backend/tests/unit/test_voice_service.py`, `backend/tests/integration/test_voice_router.py`
- Modify: `backend/app/main.py`

**Interfaces:**

```python
async def transcribe_audio(content: bytes, media_type: str, language: str = "ko") -> str: ...
def synthesize_speech(text: str) -> bytes: ...
```

- [ ] **Step 1: Write failing voice validation tests.**

```python
def test_transcription_rejects_non_audio_and_oversize_uploads():
    with pytest.raises(VoiceInputError, match="audio"):
        validate_voice_upload(b"x", "image/png", 10)

def test_speech_rejects_empty_text():
    with pytest.raises(VoiceInputError, match="text"):
        synthesize_speech(" ")
```

- [ ] **Step 2: Run the voice tests and verify they fail.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_voice_service.py tests/integration/test_voice_router.py -q`
Expected: FAIL because voice modules do not exist.

- [ ] **Step 3: Implement safe local adapters.**

Use `faster_whisper.WhisperModel(settings.whisper_model)` lazily, allow `audio/wav`, `audio/mpeg`, `audio/mp4`, `audio/webm`, enforce `VOICE_MAX_UPLOAD_MB`, and remove temporary files in `finally`. Use Piper only with the configured local voice; return `audio/wav`. Do not make OpenAI audio requests from these default routes.

- [ ] **Step 4: Run tests using fake Whisper/Piper adapters.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_voice_service.py tests/integration/test_voice_router.py -q`
Expected: PASS without downloading a model during test execution.

## Task 6: Streamlit authentication and travel-first interface

**Files:**
- Create: `frontend/core/supabase_auth.py`, `frontend/core/authenticated_api.py`, `frontend/components/voice_input.py`, `frontend/components/travel_results.py`, `frontend/tests/test_supabase_auth.py`, `frontend/tests/test_authenticated_api.py`
- Modify: `frontend/app.py`, `frontend/app_pages/12_travel_kakaomap.py`, `frontend/core/config.py`

**Interfaces:**

```python
def login(email: str, password: str) -> Session: ...
def current_access_token() -> str | None: ...
def create_travel_job(payload: dict[str, object]) -> UUID: ...
def consume_events(request_id: UUID) -> Iterator[GenerationEvent]: ...
```

- [ ] **Step 1: Write failing UI-boundary tests.**

```python
def test_authenticated_request_adds_bearer_token(monkeypatch):
    captured = {}
    request_with_auth("GET", "/api/favorites", token="jwt", sink=captured)
    assert captured["headers"]["Authorization"] == "Bearer jwt"

def test_logged_out_user_is_sent_to_login():
    assert route_for_session(None) == "00_login.py"
```

- [ ] **Step 2: Run frontend tests and verify they fail.**

Run: `cd frontend; ..\\.venv\\Scripts\\python.exe -m pytest tests/test_supabase_auth.py tests/test_authenticated_api.py -q`
Expected: FAIL because authentication helpers do not exist.

- [ ] **Step 3: Implement the travel-first UI.**

Put login/signup before all protected pages. Make the travel composer the default post-login view: text area, audio recorder/uploader, optional nights and food-preference controls, and one primary “여행 계획 만들기” button. Consume SSE progress into a Streamlit status element. Render result tabs named `일정`, `Kakao 지도`, `즐겨찾기`, and `내 여행`; use the existing safe map HTML renderer for only verified marker data. Each card has a Kakao detail link and favorite action.

- [ ] **Step 4: Run frontend tests and manual browser smoke test.**

Run: `cd frontend; ..\\.venv\\Scripts\\python.exe -m pytest tests -q`
Expected: PASS. Start both services, sign in with a disposable Supabase user, submit “부산 2박 3일, 해산물과 국밥을 좋아해”, and verify progress, cards, markers, and a persisted favorite.

## Task 7: End-to-end validation and operator documentation

**Files:**
- Modify: `README.md` if present or create `RUNBOOK.md`, `.env.example`
- Create: `backend/tests/e2e/test_travel_happy_path.py`

- [ ] **Step 1: Write the e2e happy-path test with fake Supabase/Kakao/provider/Redis services.**

```python
def test_authenticated_text_request_produces_saved_verified_trip_and_events(client, auth_headers):
    job = client.post("/api/travel-plans", json={"query": "부산 2박 3일"}, headers=auth_headers).json()
    events = list(read_sse(client, f"/api/travel-plans/{job['request_id']}/events", auth_headers))
    trip = client.get(f"/api/travel-plans/{job['request_id']}", headers=auth_headers).json()
    assert events[-1]["stage"] == "complete"
    assert all(place["kakao_place_url"].startswith("https://place.map.kakao.com/") for place in trip["places"])
```

- [ ] **Step 2: Run the test and verify it fails before wiring all fakes.**

Run: `cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests/e2e/test_travel_happy_path.py -q`
Expected: FAIL until the full pipeline is connected.

- [ ] **Step 3: Document setup and test the complete system.**

Document required Supabase dashboard steps, the exact SQL migration application, `docker compose up -d redis`, Ollama service/model checks, optional Gemini/OpenAI/Kakao key setup, and start commands. Do not print or commit real secret values.

- [ ] **Step 4: Run the complete verification suite.**

Run: `..\\.venv\\Scripts\\python.exe -m pip check; cd backend; ..\\.venv\\Scripts\\python.exe -m pytest tests -q; cd ..\\frontend; ..\\.venv\\Scripts\\python.exe -m pytest tests -q`
Expected: dependency check succeeds and all tests pass.

## Plan Self-Review

- Spec coverage: Tasks 1–2 cover configuration, Redis, ERD, and RLS; Task 3 covers JWT and persistence; Task 4 covers verified plan generation, favorites, and SSE; Task 5 covers local STT/TTS; Task 6 covers login and travel/map UI; Task 7 covers the end-to-end flow and operational instructions.
- Scope: The work is staged so Task 4 creates a text-to-map vertical slice before voice UI in Task 5–6. Gemini web grounding remains optional; Kakao is the authoritative place source.
- Type consistency: `CurrentUser`, `TravelRepository`, `GenerationStage`, `TravelPlanResult`, and the voice functions are named consistently across producing and consuming tasks.
- Placeholder scan: no implementation placeholders are used; cloud credentials remain intentionally blank because they are secrets supplied outside source control.
