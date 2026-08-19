from types import SimpleNamespace
import weakref

import pytest

from app.chat.intent_service import IntentService, _generate_with_gemini
from app.places.models import SearchIntent


def test_explicit_filters_override_generated_intent() -> None:
    service = IntentService(generator=lambda *_: SearchIntent(district="해운대", category="cafe", keyword="오션뷰"))

    intent, warning = service.interpret("맛있는 곳", [], district="서면", category="food", quick_keyword="고기")

    assert intent.district == "서면"
    assert intent.category == "food"
    assert intent.keyword == "고기"
    assert warning == ""


def test_parser_understands_korean_district_and_food_when_gemini_fails() -> None:
    def fail(*_):
        raise RuntimeError("offline")

    intent, warning = IntentService(generator=fail).interpret("광안리에서 회 맛집 찾아줘", [])

    assert intent.district == "광안리"
    assert intent.category == "food"
    assert "회" in intent.keyword
    assert warning == ""


@pytest.mark.parametrize(
    ("message", "district", "category", "keyword"),
    [
        ("해운대 오션뷰 카페 추천해줘", "해운대", "cafe", "오션뷰"),
        ("해운대 관광지 알려줘", "해운대", "attraction", ""),
        ("서면 고기 맛집 찾아줘", "서면", "food", "고기"),
        ("남포동 쇼핑 기념품 찾아줘", "남포", "shopping", "기념품"),
    ],
)
def test_explicit_user_terms_override_incorrect_generated_intent(
    message: str,
    district: str,
    category: str,
    keyword: str,
) -> None:
    wrong = SearchIntent(district="기장", category="food", keyword="돼지국밥")

    intent, warning = IntentService(generator=lambda *_: wrong).interpret(message, [])

    assert intent.district == district
    assert intent.category == category
    assert intent.keyword == keyword
    assert warning == ""


def test_follow_up_inherits_recent_context() -> None:
    recent = [SearchIntent(district="기장", category="cafe", keyword="오션뷰")]

    intent, _ = IntentService(generator=None).interpret("조용한 곳으로 더 찾아줘", recent)

    assert intent.district == "기장"
    assert intent.category == "cafe"


@pytest.mark.filterwarnings("ignore:'_UnionGenericAlias' is deprecated:DeprecationWarning")
def test_gemini_client_stays_alive_during_generation(monkeypatch) -> None:
    class FakeModels:
        def __init__(self, owner):
            self.owner = weakref.ref(owner)

        def generate_content(self, **_kwargs):
            if self.owner() is None:
                raise RuntimeError("client closed")
            return SimpleNamespace(text='{"region":"부산","district":"서면","category":"food","keyword":"고기","query":""}')

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = FakeModels(self)

    monkeypatch.setattr("google.genai.Client", FakeClient)
    monkeypatch.setattr("app.chat.intent_service.settings", SimpleNamespace(gemini_api_key="key", gemini_model="model"))

    assert _generate_with_gemini("서면 고기 맛집", []).district == "서면"
