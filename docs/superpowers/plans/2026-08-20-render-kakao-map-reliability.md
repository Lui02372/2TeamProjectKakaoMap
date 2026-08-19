# Render Kakao Map Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the embedded Kakao map initialize reliably on the Render-hosted Streamlit frontend and show a usable fallback if initialization cannot complete.

**Architecture:** Keep the existing `components.html` boundary and place data contract. Replace the one-shot blocking SDK tag with a small in-iframe loader that waits for layout, loads the Kakao SDK with an origin referrer, retries once, and relayouts the map when its container size changes.

**Tech Stack:** Python 3, Streamlit components, Kakao Maps JavaScript SDK, pytest

## Global Constraints

- Do not change backend APIs, Supabase tables, authentication, or place search.
- Keep `KAKAO_JAVASCRIPT_KEY` as the frontend environment variable.
- Do not commit any API key.
- Keep place cards and Kakao detail links usable when the map fails.

---

### Task 1: Render-safe Kakao loader contract

**Files:**
- Modify: `frontend/tests/test_guide.py`
- Modify: `frontend/components/guide_map.py`

**Interfaces:**
- Consumes: `generate_kakao_map_html(places: list[GuidePlace], javascript_key: str) -> str`
- Produces: HTML containing the same place payload plus an asynchronous SDK/layout recovery script

- [ ] **Step 1: Write the failing regression test**

Add a test asserting that generated HTML contains `referrerPolicy`, `script.onerror`, a bounded SDK timeout, a single retry path, `ResizeObserver`, `map.relayout()`, and a container-size wait while preserving the existing fallback text.

- [ ] **Step 2: Run the focused test to verify RED**

Run: `python -m pytest tests/test_guide.py -q`

Expected: the new test fails because the current HTML uses a static script tag and one-shot initialization.

- [ ] **Step 3: Implement the minimal loader**

Update `generate_kakao_map_html` so its script:

1. dynamically creates the Kakao SDK script with `autoload=false` and `referrerPolicy = "origin"`;
2. resolves only after `window.kakao.maps` exists;
3. rejects on load error or an 8-second timeout;
4. waits for a non-zero map container using `requestAnimationFrame` with a bounded timeout;
5. creates markers and bounds exactly as before;
6. attaches `ResizeObserver` and calls `map.relayout()` before restoring bounds;
7. retries initialization once, then calls the existing fallback.

- [ ] **Step 4: Run the focused test to verify GREEN**

Run: `python -m pytest tests/test_guide.py -q`

Expected: all focused frontend guide tests pass.

- [ ] **Step 5: Commit the implementation**

Commit message: `fix: recover Kakao map initialization on Render`

### Task 2: Regression and deployment verification

**Files:**
- Modify only if verification reveals a loader defect: `frontend/components/guide_map.py`
- Test only if a defect is found: `frontend/tests/test_guide.py`

**Interfaces:**
- Consumes: Render frontend `https://twoteamprojectkakaomap-1.onrender.com/`
- Consumes: Render backend `https://twoteamprojectkakaomap.onrender.com/`
- Produces: deployed map tiles and markers for returned Kakao places

- [ ] **Step 1: Run all frontend tests**

Run from `frontend`: `python -m pytest tests -q`

Expected: zero failures.

- [ ] **Step 2: Run all backend tests**

Run from `backend`: `python -m pytest tests -q`

Expected: zero failures.

- [ ] **Step 3: Verify repository integrity**

Run: `git diff --check` and `git status --short`

Expected: no whitespace errors and only intentional committed changes.

- [ ] **Step 4: Push verified HEAD to GitHub main**

Run: `git push lui02372 HEAD:main`

Expected: remote `main` advances to the implementation commit without force.

- [ ] **Step 5: Wait for Render deployment and perform live QA**

Verify backend `/health` returns 200. Open the Render frontend, log in with an educational account, run `해운대 오션뷰 카페 추천해줘`, and confirm place cards, Kakao tiles, and markers are visible. If Render has not yet deployed the pushed SHA, keep polling rather than claiming completion.
