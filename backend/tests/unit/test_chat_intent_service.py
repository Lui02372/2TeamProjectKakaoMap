from app.chat.intent_service import IntentService
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
    assert warning


def test_follow_up_inherits_recent_context() -> None:
    recent = [SearchIntent(district="기장", category="cafe", keyword="오션뷰")]

    intent, _ = IntentService(generator=None).interpret("조용한 곳으로 더 찾아줘", recent)

    assert intent.district == "기장"
    assert intent.category == "cafe"

