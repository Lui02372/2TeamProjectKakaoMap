# Render Environment Template Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mixed root environment template with separate backend and frontend templates that map directly to two Render Web Services.

**Architecture:** `backend/.env.example` owns server-only runtime configuration and secrets, while `frontend/.env.example` owns only the backend URL, Kakao JavaScript key, and frontend timeout. The existing runtime loaders continue to read the root `.env`, preserving the current local-development behavior.

**Tech Stack:** Python, pytest, python-dotenv, Render Web Services

## Global Constraints

- Remove the root `.env.example` after both service-specific templates exist.
- Never place backend secrets in `frontend/.env.example`.
- Keep all secret example values empty.
- Keep the current root `.env` runtime-loading behavior unchanged.
- Do not add actual API keys or Render credentials.

---

### Task 1: Split and validate the environment templates

**Files:**
- Create: `backend/.env.example`
- Create: `frontend/.env.example`
- Delete: `.env.example`
- Modify: `backend/tests/unit/test_environment_template.py`

**Interfaces:**
- Consumes: Environment names read by `backend/app/config.py` and `frontend/core/config.py`.
- Produces: Two service-specific key/value templates used as Render Dashboard checklists.

- [ ] **Step 1: Write the failing tests**

Replace the single-template helper and assertions with separate backend and frontend readers. Assert that the backend template contains server deployment variables but excludes `BACKEND_API_URL` and `KAKAO_JAVASCRIPT_KEY`. Assert that the frontend template contains exactly `BACKEND_API_URL`, `KAKAO_JAVASCRIPT_KEY`, and `REQUEST_TIMEOUT_SECONDS`, and contains no server secrets.

```python
def _template_values(relative_path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (PROJECT_ROOT / relative_path).read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def test_backend_environment_template_contains_only_backend_deployment_keys() -> None:
    values = _template_values("backend/.env.example")
    required = {
        "APP_ENV",
        "LLM_PROVIDER",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_AUDIENCE",
        "REDIS_URL",
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "KAKAO_REST_API_KEY",
        "KAKAO_LOCAL_BASE_URL",
        "REQUEST_TIMEOUT_SECONDS",
    }
    assert required <= values.keys()
    assert "BACKEND_API_URL" not in values
    assert "KAKAO_JAVASCRIPT_KEY" not in values


def test_frontend_environment_template_contains_only_frontend_keys() -> None:
    values = _template_values("frontend/.env.example")
    assert set(values) == {
        "BACKEND_API_URL",
        "KAKAO_JAVASCRIPT_KEY",
        "REQUEST_TIMEOUT_SECONDS",
    }
    assert values["KAKAO_JAVASCRIPT_KEY"] == ""
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"
python -m pytest backend/tests/unit/test_environment_template.py -q
```

Expected: FAIL because `backend/.env.example` and `frontend/.env.example` do not exist.

- [ ] **Step 3: Create the split templates and remove the root template**

Create `backend/.env.example` by moving all server-owned settings from the root template. Use `LLM_PROVIDER=gemini` as the deployable cloud default, leave secret values empty, and retain optional Ollama settings only as commented local alternatives.

Create `frontend/.env.example` with:

```dotenv
BACKEND_API_URL=http://127.0.0.1:8000
KAKAO_JAVASCRIPT_KEY=
REQUEST_TIMEOUT_SECONDS=60
```

Delete the root `.env.example` so there is one unambiguous template per service.

- [ ] **Step 4: Run focused and full tests**

Run:

```powershell
$env:PYTHONPATH="backend"
python -m pytest backend/tests/unit/test_environment_template.py -q
python -m pytest backend/tests -q
$env:PYTHONPATH="frontend"
python -m pytest frontend/tests -q
```

Expected: all commands PASS.

- [ ] **Step 5: Verify Git tracking and secret boundaries**

Run:

```powershell
git check-ignore -v backend/.env.example frontend/.env.example
git diff --check
git status --short
```

Expected: both example files are visible as tracked changes, actual `.env` remains ignored, and `git diff --check` exits successfully.

- [ ] **Step 6: Commit**

```powershell
git add -- backend/.env.example frontend/.env.example backend/tests/unit/test_environment_template.py .env.example
git commit -m "chore: split backend and frontend env templates"
```
