# 부산여행 가이드 실행 오류 수정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대화 질문 500 오류, 사이드바 저대비 글자, 교육용 비밀번호 제한을 수정한다.

**Architecture:** Supabase 저장소 경계에서 외부 행을 공개 Pydantic 모델 필드로 투영한다. 프론트엔드는 사이드바 텍스트와 입력 위젯 텍스트의 색상 책임을 분리한다. 인증 요청 모델의 최소 길이와 화면 안내, 예시 SQL을 같은 정책으로 맞춘다.

**Tech Stack:** FastAPI, Pydantic v2, Supabase/PostgREST, Streamlit, pytest, Argon2id

## Global Constraints

- 외부 API mock fallback을 추가하지 않는다.
- 비밀번호는 평문으로 저장하지 않고 Argon2id를 유지한다.
- `id01 / pw01`, `id02 / pw02`를 사용할 수 있어야 한다.

---

### Task 1: Supabase 대화 응답 투영

**Files:**
- Modify: `backend/app/chat/repository.py`
- Create: `backend/tests/unit/test_chat_repository.py`

**Interfaces:**
- Consumes: `ChatThread.model_fields`, `ChatMessage.model_fields`
- Produces: 추가 DB 열이 있어도 `create_thread()`와 `add_message()`가 공개 모델을 반환

- [ ] **Step 1: 추가 필드가 포함된 Supabase 행 회귀 테스트를 작성한다.**
- [ ] **Step 2: `pytest backend/tests/unit/test_chat_repository.py -v`를 실행해 검증 오류로 실패하는지 확인한다.**
- [ ] **Step 3: 모델 필드만 추출하는 `_model_payload`를 저장소에 추가하고 두 INSERT 결과에 적용한다.**
- [ ] **Step 4: 단위 테스트와 채팅 통합 테스트가 통과하는지 확인한다.**
- [ ] **Step 5: 대화 저장소 수정만 커밋한다.**

### Task 2: 사이드바 색상 대비

**Files:**
- Modify: `frontend/app.py`
- Create: `frontend/tests/test_sidebar_style.py`

**Interfaces:**
- Produces: 사이드바 제목/설명은 밝은색, 흰 배경 버튼/선택 상자는 `#073b4c`

- [ ] **Step 1: 전역 `stSidebar *` 선택자가 없고 위젯 색상이 명시되는지 검사하는 테스트를 작성한다.**
- [ ] **Step 2: 테스트가 기존 전역 선택자 때문에 실패하는지 확인한다.**
- [ ] **Step 3: 전역 선택자를 제거하고 마크다운·캡션과 위젯 색상을 분리한다.**
- [ ] **Step 4: 프론트엔드 테스트와 Streamlit 렌더링 테스트를 실행한다.**
- [ ] **Step 5: CSS 수정만 커밋한다.**

### Task 3: 교육용 비밀번호와 예시 계정 SQL

**Files:**
- Modify: `backend/app/auth/models.py`
- Modify: `frontend/app.py`
- Create: `backend/tests/unit/test_auth_models.py`
- Create: `supabase/seeds/educational_users.sql`

**Interfaces:**
- Produces: `SignupRequest`가 4자 이상을 허용하고 예시 계정 SQL이 Argon2id 해시만 저장

- [ ] **Step 1: `pw01` 허용과 3자 거부 테스트를 작성한다.**
- [ ] **Step 2: 기존 8자 제한 때문에 테스트가 실패하는지 확인한다.**
- [ ] **Step 3: 최소 길이와 프론트 안내를 4자로 변경하고 두 Argon2id 해시로 멱등 SQL을 작성한다.**
- [ ] **Step 4: 인증 및 프론트엔드 테스트를 실행한다.**
- [ ] **Step 5: 비밀번호 정책과 SQL을 커밋한다.**

### Task 4: 전체 검증

**Files:**
- Verify: `backend/tests/`
- Verify: `frontend/tests/`

**Interfaces:**
- Consumes: Task 1~3 결과
- Produces: 로컬 및 Render 재배포 가능한 검증 결과

- [ ] **Step 1: 전체 pytest를 실행한다.**
- [ ] **Step 2: 실제 Kakao 키워드 API가 200과 장소 결과를 반환하는지 확인한다.**
- [ ] **Step 3: Streamlit 화면에서 사이드바와 추천 질문 흐름을 재검증한다.**
- [ ] **Step 4: `git diff --check`와 작업 트리 상태를 확인한다.**
