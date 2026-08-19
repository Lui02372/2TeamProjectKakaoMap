from collections.abc import Callable, Sequence
import json

from app.config import settings
from app.places.models import PlaceCategory, SearchIntent


DISTRICTS = ("해운대", "광안리", "수영", "서면", "전포", "남포", "자갈치", "영도", "기장", "동래", "온천장")
CATEGORY_KEYWORDS: dict[PlaceCategory, tuple[str, ...]] = {
    "food": ("맛집", "식당", "음식", "고기", "회", "국밥", "밀면"),
    "cafe": ("카페", "커피", "브런치", "디저트"),
    "attraction": ("관광", "명소", "여행지", "볼거리", "야경"),
    "shopping": ("쇼핑", "시장", "백화점", "기념품"),
    "all": (),
}
SEARCH_KEYWORDS = (
    "돼지국밥", "밀면", "해산물", "고기", "회", "브런치", "디저트", "오션뷰",
    "야경", "해수욕장", "전망대", "시장", "백화점", "기념품",
)


def _explicit_district(message: str) -> str:
    return next((name for name in DISTRICTS if name in message), "")


def _explicit_category(message: str) -> PlaceCategory | None:
    matches = [
        (message.rfind(word), category)
        for category, words in CATEGORY_KEYWORDS.items()
        for word in words
        if word in message
    ]
    return max(matches, default=(-1, None), key=lambda item: item[0])[1]


def _explicit_keyword(message: str) -> str:
    matches = sorted((message.find(word), word) for word in SEARCH_KEYWORDS if word in message)
    return " ".join(dict.fromkeys(word for _, word in matches))


class IntentService:
    def __init__(self, generator: Callable[[str, Sequence[SearchIntent]], SearchIntent] | None = None):
        self.generator = generator

    @classmethod
    def from_settings(cls) -> "IntentService":
        return cls(_generate_with_gemini if settings.gemini_api_key and settings.gemini_model else None)

    def interpret(
        self,
        message: str,
        recent: Sequence[SearchIntent],
        *,
        district: str = "",
        category: PlaceCategory | None = None,
        quick_keyword: str = "",
    ) -> tuple[SearchIntent, str]:
        generated: SearchIntent | None = None
        if self.generator is not None:
            try:
                generated = self.generator(message, recent)
            except Exception:
                pass
        fallback = self._parse(message, recent)
        intent = generated or fallback
        explicit_district = _explicit_district(message)
        explicit_category = _explicit_category(message)
        explicit_keyword = _explicit_keyword(message)
        return SearchIntent(
            district=district or explicit_district or intent.district or fallback.district,
            category=category or explicit_category or intent.category or fallback.category,
            keyword=(
                quick_keyword
                or explicit_keyword
                or ("" if explicit_category is not None else intent.keyword or fallback.keyword)
            ),
        ), ""

    @staticmethod
    def _parse(message: str, recent: Sequence[SearchIntent]) -> SearchIntent:
        previous = recent[-1] if recent else SearchIntent()
        district = _explicit_district(message) or previous.district
        explicit_category = _explicit_category(message)
        category = explicit_category or previous.category
        explicit_keyword = _explicit_keyword(message)
        keyword = explicit_keyword or ("" if explicit_category is not None else previous.keyword or message.strip())
        return SearchIntent(district=district, category=category, keyword=keyword)


def _generate_with_gemini(message: str, recent: Sequence[SearchIntent]) -> SearchIntent:
    from google import genai
    from google.genai import types

    context = json.dumps([item.model_dump() for item in recent[-5:]], ensure_ascii=False)
    prompt = (
        "부산 여행 장소 검색 의도를 JSON으로 추출하세요. 실제 장소를 만들지 마세요. "
        "category는 food, cafe, attraction, shopping, all 중 하나입니다.\n"
        f"최근 검색: {context}\n새 질문: {message}"
    )
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=SearchIntent.model_json_schema(),
            temperature=0.1,
        ),
    )
    return SearchIntent.model_validate_json(response.text or "{}")
