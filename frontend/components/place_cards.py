"""여행 장소 카드 렌더링."""

import streamlit as st

from models.travel import TravelPlace


def render_place_cards(places: list[TravelPlace]) -> None:
    if not places:
        st.info("선택한 조건에 맞는 장소가 없습니다.")
        return

    for place in places:
        icon = "📍" if place.place_type == "landmark" else "🍽️"
        type_label = "랜드마크" if place.place_type == "landmark" else "음식점"
        with st.container(border=True):
            st.markdown(f"#### {icon} {place.name}")
            st.caption(
                f"{type_label} · {place.day}일차 {place.order}번째"
                + (f" · {place.category_name}" if place.category_name else "")
            )
            if place.description:
                st.write(place.description)
            address = place.road_address or place.address
            if address:
                st.write(f"주소: {address}")
            if place.phone:
                st.write(f"전화: {place.phone}")
            if place.safe_kakao_url:
                st.link_button("Kakao 장소 상세 보기", place.safe_kakao_url)
            if not place.has_valid_coordinates:
                st.warning("좌표가 올바르지 않아 지도에는 표시되지 않습니다.")
