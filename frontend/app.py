"""부산여행 가이드 2팀 사용자용 Streamlit 앱."""

from html import escape

import streamlit as st

from clients import guide_client
from components.guide_map import render_kakao_map
from core.api_client import BackendAPIError
from core.config import KAKAO_JAVASCRIPT_KEY
from models.guide import GuidePlace


st.set_page_config(page_title="부산여행 가이드 2팀", page_icon="🌊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  .stApp { background: linear-gradient(180deg, #f3fbff 0, #ffffff 38%); color: #15384a; }
  [data-testid="stSidebar"] { background: #073b4c; }
  [data-testid="stSidebar"] * { color: #f4fbff; }
  [data-testid="stSidebar"] .stButton button { background:#fff; color:#073b4c; border:0; font-weight:700; }
  .hero { padding:2rem 2.2rem; border-radius:24px; color:white; margin-bottom:1.2rem;
    background:linear-gradient(120deg,rgba(3,83,112,.96),rgba(0,166,166,.88)),
    radial-gradient(circle at 85% 15%,#ffd166 0,transparent 30%); box-shadow:0 16px 45px rgba(7,59,76,.18); }
  .hero h1 { margin:0 0 .45rem; font-size:2.25rem; }
  .hero p { margin:0; opacity:.94; font-size:1.05rem; }
  .eyebrow { letter-spacing:.12em; font-weight:800; font-size:.78rem; color:#ffd166; }
  .place-card { padding:1rem 1.05rem; border:1px solid #dcecf2; border-radius:18px; background:#fff;
    box-shadow:0 6px 20px rgba(21,56,74,.07); margin-bottom:.75rem; }
  .place-card h4 { margin:0 0 .3rem; color:#073b4c; }
  .place-card p { margin:.2rem 0; color:#496a78; font-size:.92rem; }
  .filter-badge { display:inline-block; background:#e5f8f6; color:#067c7c; padding:.35rem .7rem;
    border-radius:999px; margin:0 .3rem .5rem 0; font-size:.85rem; font-weight:700; }
  .welcome { padding:1.3rem; border:1px dashed #9ccbd7; border-radius:18px; background:#f8fdff; }
  div[data-testid="stChatMessage"] { border-radius:18px; border:1px solid #e2eef2; background:#fff; }
</style>
""", unsafe_allow_html=True)


REGIONS = {
    "부산 전체": "", "해운대": "해운대", "광안리·수영": "광안리", "서면·전포": "서면",
    "남포·자갈치": "남포", "영도": "영도", "기장": "기장", "동래·온천장": "동래",
}
CATEGORIES = {"전체": "all", "맛집": "food", "카페": "cafe", "관광지": "attraction", "쇼핑": "shopping"}
QUICK_KEYWORDS = ["선택 안 함", "돼지국밥", "밀면", "회·해산물", "고기", "브런치", "오션뷰 카페", "야경"]


def initialize_state() -> None:
    defaults = {
        "token": "", "user": None, "thread_id": "", "messages": [], "places": [],
        "intent": None, "favorite_ids": set(), "show_favorites": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_user_state() -> None:
    for key in ("token", "user", "thread_id", "messages", "places", "intent", "favorite_ids", "show_favorites"):
        st.session_state.pop(key, None)
    initialize_state()


def show_error(error: Exception) -> None:
    message = str(error)
    if "401" in message:
        clear_user_state()
        st.error("로그인 시간이 만료되었어요. 다시 로그인해 주세요.")
    else:
        st.error(message)


def store_session(session) -> None:
    st.session_state.token = session.access_token
    st.session_state.user = session.user.model_dump(mode="json")
    try:
        favorites = guide_client.list_favorites(session.access_token)
        st.session_state.favorite_ids = {str(place.id) for place in favorites}
    except BackendAPIError:
        st.session_state.favorite_ids = set()


def render_auth() -> None:
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.markdown("""
        <div class="hero" style="min-height:360px;display:flex;flex-direction:column;justify-content:center">
          <div class="eyebrow">BUSAN TRAVEL COMPANION</div>
          <h1>부산여행 가이드 2팀</h1>
          <p>궁금한 부산 여행을 편하게 물어보세요.<br>실제 카카오맵 장소를 지도와 함께 찾아드려요.</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("#### 🌊 한 번에 만나는 부산")
        st.write("지역과 취향을 고르거나, ‘광안리 회 맛집 알려줘’처럼 자연스럽게 질문해 보세요.")
    with right:
        st.markdown("### 반가워요 👋")
        st.caption("교육용 서비스이므로 이메일 없이 아이디로 시작할 수 있어요.")
        login_tab, signup_tab = st.tabs(["로그인", "처음 시작하기"])
        with login_tab:
            with st.form("login_form"):
                username = st.text_input("아이디", placeholder="busan02")
                password = st.text_input("비밀번호", type="password")
                submitted = st.form_submit_button("부산 여행 시작하기", use_container_width=True, type="primary")
            if submitted:
                try:
                    store_session(guide_client.login(username, password))
                    st.rerun()
                except (BackendAPIError, ValueError) as error:
                    show_error(error)
        with signup_tab:
            with st.form("signup_form"):
                new_username = st.text_input("사용할 아이디", placeholder="영문, 숫자, 밑줄 4~30자")
                display_name = st.text_input("여행자 이름", placeholder="부산 탐험가")
                new_password = st.text_input("비밀번호", type="password", help="8자 이상 입력해 주세요.")
                password_confirm = st.text_input("비밀번호 확인", type="password")
                joined = st.form_submit_button("계정 만들기", use_container_width=True, type="primary")
            if joined:
                if new_password != password_confirm:
                    st.error("비밀번호 확인이 일치하지 않아요.")
                else:
                    try:
                        store_session(guide_client.signup(new_username, new_password, display_name))
                        st.rerun()
                    except (BackendAPIError, ValueError) as error:
                        show_error(error)


def update_place_favorite(place_id: str, favorite: bool) -> None:
    token = st.session_state.token
    if favorite:
        guide_client.add_favorite(token, place_id)
        st.session_state.favorite_ids.add(place_id)
    else:
        guide_client.delete_favorite(token, place_id)
        st.session_state.favorite_ids.discard(place_id)


def render_place_card(place: GuidePlace, index: int) -> None:
    place_id = str(place.id)
    is_favorite = place_id in st.session_state.favorite_ids
    st.markdown(
        f"<div class='place-card'><h4>{'⭐' if is_favorite else '📍'} {escape(place.name)}</h4>"
        f"<p>{escape(place.category_name or '부산 추천 장소')}</p>"
        f"<p>📌 {escape(place.road_address or place.address or '주소 정보 없음')}</p>"
        f"<p>{escape('☎ ' + place.phone if place.phone else '')}</p></div>",
        unsafe_allow_html=True,
    )
    action, link = st.columns([1, 1])
    with action:
        label = "즐겨찾기 해제" if is_favorite else "즐겨찾기"
        if st.button(label, key=f"favorite-{place_id}-{index}", use_container_width=True):
            try:
                update_place_favorite(place_id, not is_favorite)
                st.rerun()
            except BackendAPIError as error:
                show_error(error)
    with link:
        if place.safe_kakao_url:
            st.link_button("카카오맵 보기", place.safe_kakao_url, use_container_width=True)


initialize_state()

if not st.session_state.token:
    render_auth()
    st.stop()

user = st.session_state.user
with st.sidebar:
    st.markdown("## 🌊 부산여행 가이드")
    st.caption("2팀 · 나만의 부산 여행 친구")
    st.markdown(f"### {user['display_name']}님")
    st.caption(f"@{user['username']}")
    if st.button("로그아웃", use_container_width=True):
        try:
            guide_client.logout(st.session_state.token)
        except BackendAPIError:
            pass
        clear_user_state()
        st.rerun()

    st.divider()
    st.markdown("#### 어디를 둘러볼까요?")
    region_label = st.selectbox("부산 지역", list(REGIONS), label_visibility="collapsed")
    category_label = st.selectbox("장소 종류", list(CATEGORIES), label_visibility="collapsed")
    quick_label = st.selectbox("빠른 키워드", QUICK_KEYWORDS, label_visibility="collapsed")
    district = REGIONS[region_label]
    category = CATEGORIES[category_label]
    quick_keyword = "" if quick_label == "선택 안 함" else quick_label.replace("·", " ").replace(" 카페", "")

    if st.button("🔎 선택 조건으로 찾기", use_container_width=True, type="primary"):
        try:
            result = guide_client.search(st.session_state.token, district, category, quick_keyword)
            st.session_state.places = result.places
            st.session_state.intent = result.intent
            st.session_state.show_favorites = False
            if result.warning:
                st.warning(result.warning)
        except BackendAPIError as error:
            show_error(error)

    if st.button("⭐ 내 즐겨찾기", use_container_width=True):
        try:
            st.session_state.places = guide_client.list_favorites(st.session_state.token)
            st.session_state.show_favorites = True
        except BackendAPIError as error:
            show_error(error)

    if st.button("💬 새 여행 대화", use_container_width=True):
        st.session_state.thread_id = ""
        st.session_state.messages = []
        st.session_state.places = []
        st.session_state.intent = None
        st.session_state.show_favorites = False
        st.rerun()

st.markdown("""
<div class="hero"><div class="eyebrow">BUSAN TRAVEL GUIDE · TEAM 2</div>
<h1>부산에서 오늘, 어디로 갈까요?</h1>
<p>먹고 싶은 것과 가고 싶은 동네를 말하면 실제 장소를 지도에서 찾아드려요.</p></div>
""", unsafe_allow_html=True)

suggestion_prompt = None
suggestions = ["서면 고기 맛집 찾아줘", "해운대 오션뷰 카페 추천해줘", "광안리 야경 코스 알려줘"]
suggestion_cols = st.columns(3)
for index, suggestion in enumerate(suggestions):
    with suggestion_cols[index]:
        if st.button(suggestion, key=f"suggestion-{index}", use_container_width=True):
            suggestion_prompt = suggestion

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

prompt = st.chat_input("예: 광안리에서 회 맛집 찾아줘") or suggestion_prompt
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    try:
        if not st.session_state.thread_id:
            st.session_state.thread_id = str(guide_client.create_thread(st.session_state.token).id)
        response = guide_client.ask(
            st.session_state.token, st.session_state.thread_id, prompt,
            district=district, category=None if category == "all" else category, quick_keyword=quick_keyword,
        )
        st.session_state.messages.append({"role": "assistant", "content": response.answer})
        st.session_state.places = response.places
        st.session_state.intent = response.intent
        st.session_state.show_favorites = False
        if response.warning:
            st.session_state.messages.append({"role": "assistant", "content": response.warning})
        st.rerun()
    except BackendAPIError as error:
        show_error(error)

intent = st.session_state.intent
if intent:
    badges = [intent.district or "부산 전체", CATEGORIES and next((label for label, value in CATEGORIES.items() if value == intent.category), "전체")]
    if intent.keyword:
        badges.append(intent.keyword)
    st.markdown("".join(f"<span class='filter-badge'>{escape(badge)}</span>" for badge in badges), unsafe_allow_html=True)

places: list[GuidePlace] = st.session_state.places
if places:
    title = "⭐ 저장한 장소" if st.session_state.show_favorites else f"찾은 장소 {len(places)}곳"
    st.markdown(f"### {title}")
    map_col, result_col = st.columns([1.25, 1], gap="large")
    with map_col:
        render_kakao_map(places, KAKAO_JAVASCRIPT_KEY)
    with result_col:
        for index, place in enumerate(places):
            render_place_card(place, index)
elif not st.session_state.messages:
    st.markdown("""
    <div class="welcome"><h3>✨ 이렇게 시작해 보세요</h3>
    <p>왼쪽에서 지역과 카테고리를 고른 뒤 바로 찾거나, 위 추천 질문을 눌러보세요.</p>
    <p>“부산 어디 지역이 좋아?”, “기장 가족 여행 코스”, “남포동 돼지국밥”처럼 자유롭게 물어봐도 좋아요.</p></div>
    """, unsafe_allow_html=True)
