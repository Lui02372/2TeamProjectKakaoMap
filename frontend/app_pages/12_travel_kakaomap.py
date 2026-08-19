"""Provider별 여행 계획을 비교하고 장소를 Kakao 지도에 표시한다."""

import streamlit as st
from pydantic import ValidationError

from clients.travel_client import compare_travel_plans
from components.kakao_map import render_kakao_map
from components.place_cards import render_place_cards
from core.api_client import BackendAPIError
from core.config import KAKAO_JAVASCRIPT_KEY
from models.travel import ProviderTravelResult, filter_places


st.title("🗺️ 여행 지도 Agent")
st.caption("여러 Provider의 구조화 여행 계획을 비교하고 실제 장소를 지도에서 확인합니다.")

for key, default in {
    "travel_response": None,
    "travel_last_payload": None,
    "travel_last_error": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.form("travel-compare-form"):
    message = st.text_area(
        "여행 요청",
        value="부산에 2박 3일 여행을 가고 싶어. 바다와 현지 음식을 좋아해.",
        height=110,
    )
    providers = st.multiselect(
        "비교할 Provider",
        options=["mock", "gemini", "openai", "ollama"],
        default=["mock"],
    )
    count_left, count_right = st.columns(2)
    with count_left:
        landmark_count = st.number_input(
            "랜드마크 추천 개수", min_value=1, max_value=10, value=6, step=1
        )
    with count_right:
        food_count = st.number_input(
            "음식점 추천 개수", min_value=1, max_value=10, value=4, step=1
        )
    cloud_calls = sum(provider in {"gemini", "openai"} for provider in providers)
    st.info(f"Backend 요청 1회 · Provider 처리 {len(providers)}회 · Cloud API 최대 {cloud_calls}회")
    submitted = st.form_submit_button(
        "여행 계획 비교", type="primary", disabled=not message.strip() or not providers
    )

if submitted:
    try:
        with st.spinner("Provider별 여행 계획을 만들고 있습니다..."):
            response = compare_travel_plans(
                message, providers, int(landmark_count), int(food_count)
            )
        st.session_state.travel_response = response
        st.session_state.travel_last_payload = {
            "message": message.strip(),
            "providers": providers,
            "landmark_count": int(landmark_count),
            "food_count": int(food_count),
        }
        st.session_state.travel_last_error = None
    except (BackendAPIError, ValidationError, ValueError) as error:
        st.session_state.travel_last_error = str(error)

if st.session_state.travel_last_error:
    st.error(st.session_state.travel_last_error)
    if st.session_state.travel_response is not None:
        st.caption("현재 요청은 실패하여 아래에는 마지막 정상 결과를 유지합니다.")

response = st.session_state.travel_response
if response is None:
    st.info("요청을 보내면 Provider 비교 결과와 여행 지도가 여기에 표시됩니다.")
    st.stop()

st.divider()
st.subheader("Provider 비교")
tabs = st.tabs([result.provider for result in response.results])
for tab, result in zip(tabs, response.results):
    with tab:
        if result.status == "success" and result.content:
            landmark_total = len(result.content.landmarks)
            food_total = len(result.content.foods)
            st.success("구조화 결과 검증 성공")
            st.caption(f"{result.model or '모델 정보 없음'} · {result.latency_ms:.0f} ms")
            metric_left, metric_right = st.columns(2)
            metric_left.metric("랜드마크", f"{landmark_total} / {response.landmark_count}개")
            metric_right.metric("음식점", f"{food_total} / {response.food_count}개")
        else:
            st.error(result.error or "Provider 처리에 실패했습니다.")
            st.caption(f"{result.model or '모델 정보 없음'} · {result.latency_ms:.0f} ms")
        for warning in result.warnings:
            st.warning(warning)
        with st.expander("원본 구조화 JSON"):
            st.json(result.model_dump(mode="json"))

successful: list[ProviderTravelResult] = response.successful_results
if not successful:
    st.error("성공한 Provider가 없어 여행 결과와 지도를 표시할 수 없습니다.")
    st.stop()

st.divider()
st.subheader("여행 결과")
provider_names = [result.provider for result in successful]
selected_name = st.selectbox("지도에 표시할 Provider", provider_names)
selected = next(result for result in successful if result.provider == selected_name)
content = selected.content
assert content is not None

summary_left, summary_right = st.columns([2, 1])
with summary_left:
    st.markdown(f"### {content.destination} · {content.nights}박 {content.days}일")
    st.write(content.summary or "여행 요약이 없습니다.")
with summary_right:
    all_places = content.normalized_places()
    valid_map_count = sum(place.has_valid_coordinates for place in all_places)
    st.metric("추천 장소", f"{len(all_places)}개")
    st.caption(f"지도 표시 가능 {valid_map_count}개")

filter_left, filter_right = st.columns(2)
with filter_left:
    day_label = st.selectbox("일차", ["전체", *[f"{day}일차" for day in range(1, content.days + 1)]])
with filter_right:
    type_label = st.selectbox("장소 유형", ["전체", "랜드마크", "음식점"])
selected_day = None if day_label == "전체" else int(day_label.removesuffix("일차"))
type_value = {"전체": "all", "랜드마크": "landmark", "음식점": "food"}[type_label]
filtered = filter_places(all_places, selected_day, type_value)

cards_column, map_column = st.columns([1, 1.35], gap="large")
with cards_column:
    st.markdown(f"#### 장소 카드 · {len(filtered)}개")
    render_place_cards(filtered)
with map_column:
    st.markdown("#### Kakao 지도")
    invalid_count = sum(not place.has_valid_coordinates for place in filtered)
    if invalid_count:
        st.warning(f"좌표가 올바르지 않은 {invalid_count}개 장소는 지도에서 제외했습니다.")
    render_kakao_map(filtered, KAKAO_JAVASCRIPT_KEY)
