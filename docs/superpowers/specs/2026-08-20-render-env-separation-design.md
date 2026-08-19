# Render 환경 변수 예시 파일 분리 설계

## 목표

통합 루트 `.env.example`을 백엔드와 프론트엔드 예시 파일로 완전히 분리한다. 각 파일은 해당 Render Web Service에 등록할 변수만 포함하며, 백엔드 비밀키가 프론트엔드 설정에 섞이지 않게 한다.

## 선택한 구조

```text
backend/.env.example
frontend/.env.example
```

루트 `.env.example`은 제거한다. 실제 비밀값이 들어가는 `.env` 파일은 계속 Git에서 제외한다.

## 백엔드 파일

`backend/.env.example`에는 다음 범주만 둔다.

- 실행 환경과 기본 LLM Provider
- Supabase 서버 설정과 서비스 역할 키
- Redis 또는 Upstash 서버 설정
- OpenAI·Gemini 등 서버에서 호출하는 외부 API 설정
- Kakao Local REST API 설정
- 서버 요청 제한과 미디어 처리 설정

`KAKAO_JAVASCRIPT_KEY`와 `BACKEND_API_URL`은 포함하지 않는다.

Render 백엔드에서는 `LLM_PROVIDER=gemini`를 예시 기본값으로 사용하고, 로컬 주소에 의존하는 Ollama는 설명용 선택 항목으로만 남긴다.

## 프론트엔드 파일

`frontend/.env.example`에는 다음 변수만 둔다.

- `BACKEND_API_URL`
- `KAKAO_JAVASCRIPT_KEY`
- `REQUEST_TIMEOUT_SECONDS`

LLM API 키, Kakao REST 키, Supabase 서비스 역할 키는 포함하지 않는다.

## 로컬과 Render 사용 방식

- Render에서는 예시 파일을 업로드하지 않고 각 서비스의 Environment 화면에 해당 파일의 변수만 등록한다.
- 로컬에서는 각 예시 파일을 참고해 셸 환경 변수 또는 로컬 `.env`를 구성한다.
- 현재 코드가 루트 `.env`를 읽는 동작은 이번 작업에서 변경하지 않아 기존 로컬 실행을 깨뜨리지 않는다.

## 검증

- 백엔드 예시 파일에 프론트 전용 변수가 없는지 검사한다.
- 프론트 예시 파일에 서버 비밀키가 없는지 검사한다.
- 두 파일의 변수명이 실제 설정 코드와 일치하는지 검사한다.
- `.gitignore`가 실제 `.env` 파일은 제외하고 두 `.env.example` 파일은 추적하도록 유지되는지 확인한다.
- 기존 백엔드·프론트엔드 자동 테스트를 실행한다.

## 범위 제외

- Render 서비스 자체 생성
- 실제 API 키 입력
- `/api/travel-plans/compare` 구현
- 프론트엔드와 백엔드 런타임 설정 로더 변경
