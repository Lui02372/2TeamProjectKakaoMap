# 부산여행 가이드 사이드바 디자인 점검

- 대상: Streamlit 앱 UI
- 분류: APP UI
- 수정 전 증거: `C:/Users/CKH/Documents/ShareX/Screenshots/2026-08/chrome_VeOWygFotR.png`
- 수정 후 증거: `.gstack/design-reports/screenshots/sidebar-after.png`

## 결과

### FINDING-001 — 사이드바 입력 요소의 텍스트 대비 부족

- 영향: 높음
- 관찰: 사이드바 전체 하위 요소에 흰색 글자를 강제해 흰 배경의 버튼과 선택 상자 내용이 보이지 않았다.
- 수정: 제목과 캡션만 밝게 유지하고 버튼 및 선택 상자 글자를 `#073b4c`로 분리했다.
- 상태: verified
- 커밋: `6b4c9c0`

### FINDING-002 — 지도 SDK 도메인 불일치

- 영향: 높음
- 관찰: 장소 목록은 표시되지만 Kakao SDK가 `domain mismatched`로 차단되어 지도 fallback이 표시된다.
- 수정: 외부 설정 필요. Kakao JavaScript SDK 도메인에 `http://127.0.0.1:8501`과 Render 프론트 주소를 등록해야 한다.
- 상태: deferred

## 점수

- Design Score: D → B
- AI Slop Score: C → C
- Goodwill: 50 → 75
- 빠른 개선: 위젯 대비 수정 완료, 오류 없는 추천 검색 완료, 지도 도메인 등록 대기

