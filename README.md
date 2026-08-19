# 부산여행 가이드 2팀

아이디로 로그인한 사용자가 부산 지역·카테고리를 선택하거나 AI에게 자연어로 질문하면, Kakao Local API의 실제 장소를 카드와 Kakao 지도에서 확인하고 즐겨찾기에 저장하는 서비스입니다.

## 1. 로컬 환경 파일

PowerShell에서 프로젝트 루트 기준으로 실행합니다.

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

`backend/.env`에 최소한 아래 값을 입력합니다.

```dotenv
SUPABASE_URL=https://프로젝트.supabase.co
SUPABASE_SERVICE_ROLE_KEY=백엔드_전용_서비스_롤_키
GEMINI_API_KEY=Gemini_API_키
GEMINI_MODEL=gemini-2.5-flash
KAKAO_REST_API_KEY=카카오_REST_API_키
SESSION_TTL_HOURS=168
```

`frontend/.env`에는 공개 가능한 연결값만 입력합니다.

```dotenv
BACKEND_API_URL=http://127.0.0.1:8000
KAKAO_JAVASCRIPT_KEY=카카오_JavaScript_키
REQUEST_TIMEOUT_SECONDS=60
```

Service Role Key, Gemini Key, Kakao REST Key를 `frontend/.env`에 넣지 마세요.

## 2. Supabase 테이블 생성

Supabase Dashboard의 SQL Editor에서 [`supabase/migrations/0002_busan_guide.sql`](supabase/migrations/0002_busan_guide.sql)을 실행합니다. 이 파일은 사용자·세션·대화·검색·장소·즐겨찾기·여행 계획 관계를 생성하고, 브라우저의 직접 접근을 막는 RLS를 활성화합니다.

## 3. 패키지 설치

```powershell
python -m pip install -r requirements.txt
```

## 4. 백엔드 실행

첫 번째 PowerShell 창에서:

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

확인 주소:

- 서비스: `http://127.0.0.1:8000/`
- 상태 확인: `http://127.0.0.1:8000/health`
- API 문서: `http://127.0.0.1:8000/docs`

## 5. 프론트엔드 실행

두 번째 PowerShell 창에서 프로젝트 루트 기준으로:

```powershell
python -m streamlit run frontend/app.py --server.address 0.0.0.0 --server.port 8501
```

브라우저에서 `http://127.0.0.1:8501`을 열고 회원가입 후 사용할 수 있습니다.

## 6. 자동 테스트

백엔드와 프론트엔드는 Python import 이름 충돌을 피하기 위해 각 폴더에서 나누어 실행합니다.

```powershell
cd backend
python -m pytest tests -q
cd ../frontend
python -m pytest tests -q
```
