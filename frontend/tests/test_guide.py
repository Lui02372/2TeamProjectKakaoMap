from pathlib import Path

from streamlit.testing.v1 import AppTest

from clients import guide_client
from components.guide_map import generate_kakao_map_html
from models.guide import GuidePlace, SessionData


def place(**overrides) -> GuidePlace:
    data = {
        "id": "00000000-0000-0000-0000-000000000001",
        "kakao_place_id": "1",
        "name": "해운대해수욕장",
        "latitude": 35.1587,
        "longitude": 129.1604,
        "kakao_place_url": "https://place.map.kakao.com/1",
    }
    data.update(overrides)
    return GuidePlace.model_validate(data)


def test_session_and_place_models_validate_backend_contract() -> None:
    session = SessionData.model_validate({
        "access_token": "token", "token_type": "bearer", "expires_at": "2030-01-01T00:00:00Z",
        "user": {"id": "00000000-0000-0000-0000-000000000002", "username": "busan02", "display_name": "여행자"},
    })
    assert session.user.display_name == "여행자"
    assert place().safe_kakao_url == "https://place.map.kakao.com/1"
    assert place(kakao_place_url="javascript:alert(1)").safe_kakao_url == ""


def test_authenticated_client_sends_bearer_token(monkeypatch) -> None:
    calls = []

    def fake_request(method, path, json=None, headers=None):
        calls.append((method, path, json, headers))
        return {"id": "00000000-0000-0000-0000-000000000003", "title": "새 부산 여행 대화"}

    monkeypatch.setattr(guide_client, "request", fake_request)
    guide_client.create_thread("secret-token")

    assert calls[0][3] == {"Authorization": "Bearer secret-token"}


def test_map_serialization_escapes_untrusted_place_text() -> None:
    html = generate_kakao_map_html([place(name="</script><script>alert(1)</script>")], "validKey_123")
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html


def test_map_html_recovers_from_slow_render_sdk_and_layout() -> None:
    html = generate_kakao_map_html([place()], "validKey_123")

    assert 'script.referrerPolicy="origin"' in html
    assert "script.onerror" in html
    assert "SDK_TIMEOUT_MS=8000" in html
    assert "MAX_INIT_ATTEMPTS=2" in html
    assert "requestAnimationFrame" in html
    assert "ResizeObserver" in html
    assert "map.relayout()" in html
    assert "지도를 불러오지 못했습니다. 아래 장소 카드를 이용해 주세요." in html


def test_map_html_bounds_kakao_maps_load_callback_wait() -> None:
    html = generate_kakao_map_html([place()], "validKey_123")

    assert "MAP_LOAD_TIMEOUT_MS=8000" in html
    assert "Kakao map initialization timeout" in html


def test_main_app_is_consumer_facing() -> None:
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "부산여행 가이드 2팀" in source
    for developer_term in ("Mini Agent", "Provider 비교", "Pydantic", "원본 JSON"):
        assert developer_term not in source
    assert 'category=None if category == "all" else category' in source


def test_logged_out_app_renders_account_tabs_without_exception() -> None:
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=10).run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["로그인", "처음 시작하기"]
