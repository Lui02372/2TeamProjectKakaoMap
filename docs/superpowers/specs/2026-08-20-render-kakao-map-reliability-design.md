# Render Kakao Map Reliability Design

## Goal

로컬과 동일한 Kakao JavaScript 키와 장소 데이터를 사용하는 Render 프론트엔드에서도 지도가 안정적으로 초기화되고, 초기화 실패 시 사용자가 원인을 알 수 있는 안내를 표시한다.

## Confirmed Evidence

- Render 백엔드의 `/health`는 정상 응답한다.
- Render 백엔드는 Kakao Local API에서 장소와 유효한 위도·경도를 반환한다.
- Kakao JavaScript SDK는 로컬 주소와 Render 프론트 주소 모두에서 같은 정상 스크립트를 반환한다.
- 현재 지도 HTML은 외부 SDK 태그 직후 한 번만 `kakao.maps.load`를 호출한다. SDK 오류, 느린 로드, 크기가 확정되지 않은 iframe에 대한 재시도와 복구가 없다.

## Selected Approach

기존 `streamlit.components.v1.html` 구조는 유지하고 `frontend/components/guide_map.py`의 브라우저 로더만 강화한다.

1. Kakao SDK를 동적 script 요소로 로드하고 `referrerPolicy = "origin"`을 명시한다.
2. 기존 SDK가 있으면 재사용하고, 없으면 `load`, `error`, 제한 시간 경로를 구분한다.
3. iframe 지도 요소의 실제 너비와 높이가 확보된 뒤 지도를 생성한다.
4. 마커와 bounds 적용 후 `ResizeObserver`에서 `map.relayout()`과 bounds 재적용을 수행한다.
5. SDK 또는 초기화 실패 시 한 번만 재시도하고, 최종 실패 시 장소 카드는 유지하면서 지도 영역에 사용자용 안내를 표시한다.

## Boundaries

- 백엔드 API, Supabase 스키마, 인증, 장소 검색 로직은 변경하지 않는다.
- Kakao 이외의 지도 공급자로 교체하지 않는다.
- 비밀 키를 프론트 코드나 Git에 저장하지 않는다.
- Render 환경변수 이름은 `KAKAO_JAVASCRIPT_KEY`를 유지한다.

## Error Handling

- SDK 네트워크 오류, SDK 전역 객체 부재, 초기화 예외, 컨테이너 크기 제한 시간을 각각 최종 fallback 경로로 연결한다.
- 사용자에게는 내부 오류나 키 값을 노출하지 않고 "지도를 불러오지 못했습니다. 장소 카드를 이용해 주세요."라는 동일한 안내를 제공한다.
- 장소 카드와 Kakao 상세 링크는 지도 실패와 독립적으로 계속 작동한다.

## Testing

- 생성 HTML에 동적 SDK 로더, origin referrer policy, 오류 처리, 제한 시간, 크기 대기, `ResizeObserver`, `relayout`이 포함되는지 회귀 테스트를 먼저 작성한다.
- 기존 직렬화·키 검증·사이드바·전체 프론트 테스트를 실행한다.
- 전체 백엔드 테스트도 실행해 배포 회귀가 없음을 확인한다.
- GitHub `main` 푸시 후 Render 배포 완료를 기다리고, 실제 프론트 주소에서 로그인·검색·지도 타일·마커를 확인한다.
