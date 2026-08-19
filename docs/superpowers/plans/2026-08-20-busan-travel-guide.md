# Busan Travel Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable, login-protected Busan travel guide whose AI chat and filters return real Kakao places on a Kakao map with per-user favorites.

**Architecture:** FastAPI owns credentials, custom username/password sessions, Supabase persistence, Gemini intent extraction, and Kakao Local search. Streamlit calls only authenticated backend endpoints and presents a Korean consumer UI. Repository interfaces keep tests independent of external services while production always uses configured real services.

**Tech Stack:** Python, FastAPI, Pydantic, Argon2id, Supabase PostgreSQL, Gemini, Kakao Local REST/JavaScript SDK, Streamlit, pytest

## Global Constraints

- Render deployment is excluded; both processes must run locally first.
- Runtime must not use mock providers or fake place data.
- Passwords are stored only as Argon2id PHC strings; session tokens are stored only as SHA-256 hashes.
- The frontend never receives Supabase Service Role, Gemini, or Kakao REST credentials.
- Place facts and coordinates come only from Kakao Local API.
- User-facing pages do not expose provider/model/Pydantic/raw JSON controls.

---

## File map

- `supabase/migrations/0002_busan_guide.sql`: normalized application tables, keys, checks, indexes, and locked-down RLS.
- `backend/app/auth/*`: auth contracts, password/token primitives, Supabase repository, service, and dependency.
- `backend/app/places/*`: Kakao-backed place contracts, persistence, filtering, and search orchestration.
- `backend/app/chat/*`: Gemini intent extraction, deterministic failure fallback, conversation persistence, and orchestration.
- `backend/app/favorites/*`: user-scoped favorite persistence and API contracts.
- `backend/app/routers/*`: thin HTTP adapters for auth, chat, places, and favorites.
- `frontend/clients/guide_client.py`: authenticated backend client.
- `frontend/models/guide.py`: validated frontend response models.
- `frontend/components/guide_map.py`: Kakao JavaScript map component.
- `frontend/app.py`: login/signup and the complete consumer travel experience.

### Task 1: Normalized database and secure authentication

**Files:**
- Create: `supabase/migrations/0002_busan_guide.sql`
- Create: `backend/app/auth/models.py`
- Create: `backend/app/auth/password.py`
- Create: `backend/app/auth/repository.py`
- Create: `backend/app/auth/service.py`
- Modify: `backend/app/routers/auth_router.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `requirements.txt`
- Test: `backend/tests/unit/test_auth_password.py`
- Test: `backend/tests/unit/test_database_schema.py`
- Test: `backend/tests/integration/test_auth_router.py`

**Interfaces:**
- Produces: `AuthService.signup`, `login`, `authenticate`, `logout`; `require_current_session`; bearer `SessionResponse`.
- Consumes: configured `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SESSION_TTL_HOURS`.

- [ ] Write tests asserting normalized usernames, `$argon2id$` hashes, token hashing, expired/revoked rejection, and generic bad-login responses.
- [ ] Run `python -m pytest backend/tests/unit/test_auth_password.py backend/tests/integration/test_auth_router.py -q`; expect failures for missing auth package.
- [ ] Implement exact request constraints: username `^[a-z0-9_]{4,30}$`, password length `8..128`, display name length `1..40`; use `argon2.PasswordHasher` and `secrets.token_urlsafe(32)`.
- [ ] Implement Supabase table operations and `POST /signup`, `POST /login`, `POST /logout`, `GET /me`, plus compatibility `GET /session/verify`.
- [ ] Add SQL assertions for all ten tables, composite keys, FK delete actions, checks, and indexes; run the three test files until green.
- [ ] Commit with `feat: add secure local guide authentication`.

### Task 2: Real Kakao place search and persistence

**Files:**
- Create: `backend/app/places/models.py`
- Create: `backend/app/places/repository.py`
- Create: `backend/app/places/service.py`
- Create: `backend/app/routers/place_router.py`
- Modify: `backend/app/clients/kakao_local_client.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_place_search_service.py`
- Test: `backend/tests/integration/test_place_router.py`

**Interfaces:**
- Consumes: `CurrentSession`, `KakaoLocalClient.search_keyword(query, category_group_code, size)`.
- Produces: `PlaceSearchService.search(SearchRequest) -> SearchResponse` and `POST /api/places/search`.

- [ ] Write failing tests for category mapping, explicit district/category priority, 부산 address filtering, Kakao ID deduplication, and x/y coordinate conversion.
- [ ] Run `python -m pytest backend/tests/unit/test_place_search_service.py -q`; expect import failure.
- [ ] Implement category groups `FD6`, `CE7`, `AT4`, and optional empty group; build queries from `부산 + district + keyword` and reject non-Busan documents.
- [ ] Upsert Kakao facts by `kakao_place_id`, persist search/result ranks, and return only validated `GuidePlace` objects.
- [ ] Add the protected route and application lifespan wiring; run unit and integration tests until green.
- [ ] Commit with `feat: add Kakao-backed Busan place search`.

### Task 3: Contextual Gemini chat

**Files:**
- Create: `backend/app/chat/models.py`
- Create: `backend/app/chat/intent_service.py`
- Create: `backend/app/chat/repository.py`
- Create: `backend/app/chat/service.py`
- Create: `backend/app/routers/chat_router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_chat_intent_service.py`
- Test: `backend/tests/integration/test_chat_router.py`

**Interfaces:**
- Consumes: `PlaceSearchService.search`, current user ID, recent `ChatMessage` records, `GEMINI_API_KEY` and `GEMINI_MODEL`.
- Produces: thread list/create/messages endpoints and `ChatResponse(answer, intent, places, warning)`.

- [ ] Write failing tests that explicit UI filters override model fields, follow-up text inherits recent district/category, valid Gemini JSON is accepted, and Gemini errors use parsed user text without invented places.
- [ ] Run `python -m pytest backend/tests/unit/test_chat_intent_service.py backend/tests/integration/test_chat_router.py -q`; expect missing modules.
- [ ] Implement Pydantic `SearchIntent`, Gemini JSON-schema generation, Korean district/category parsing fallback, and safe Korean answer composition from Kakao result names.
- [ ] Persist threads/messages/search linkage and enforce thread ownership on every operation.
- [ ] Wire protected endpoints and run the two test files until green.
- [ ] Commit with `feat: add contextual Busan travel chat`.

### Task 4: User-scoped favorites

**Files:**
- Create: `backend/app/favorites/models.py`
- Create: `backend/app/favorites/repository.py`
- Create: `backend/app/routers/favorite_router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_favorite_router.py`

**Interfaces:**
- Consumes: current user ID and persisted place UUID.
- Produces: `GET /api/favorites`, `POST /api/favorites/{place_id}`, `DELETE /api/favorites/{place_id}`.

- [ ] Write failing tests for add/list/delete, duplicate add idempotency, and cross-user isolation.
- [ ] Run `python -m pytest backend/tests/integration/test_favorite_router.py -q`; expect missing routes.
- [ ] Implement repository and routes with composite-key upsert/delete filtered by authenticated `user_id`.
- [ ] Run the favorite test file until green and commit with `feat: add user place favorites`.

### Task 5: Consumer Streamlit experience and local verification

**Files:**
- Create: `frontend/models/guide.py`
- Create: `frontend/clients/guide_client.py`
- Create: `frontend/components/guide_map.py`
- Replace: `frontend/app.py`
- Modify: `frontend/.env.example`
- Create: `frontend/tests/test_guide.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: all `/api/auth`, `/api/chat`, `/api/places`, and `/api/favorites` contracts plus `KAKAO_JAVASCRIPT_KEY`.
- Produces: login/signup, sidebar filters, AI chat, map markers, result cards, favorites view, session expiry handling, and exact local run instructions.

- [ ] Write failing tests for response parsing, authorization headers, safe map serialization, Korean branding, and absence of developer menu strings.
- [ ] Run `python -m pytest frontend/tests/test_guide.py -q`; expect missing modules or old branding.
- [ ] Implement authenticated client and typed models; raise a dedicated unauthorized error on HTTP 401.
- [ ] Build the responsive Streamlit page with account screen, regions/categories/quick keywords, chat, cards, favorite controls, Kakao map, and cleared state on logout.
- [ ] Document `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` from `backend` and `python -m streamlit run frontend/app.py --server.address 0.0.0.0 --server.port 8501` from repository root.
- [ ] Run `python -m pytest backend/tests frontend/tests -q`, import checks, and local health/startup smoke checks; expect all automated tests green and both servers listening.
- [ ] Commit with `feat: deliver local Busan travel guide experience`.

