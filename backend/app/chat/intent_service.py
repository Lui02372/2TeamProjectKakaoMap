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
        warning = ""
        generated: SearchIntent | None = None
        if self.generator is not None:
            try:
                generated = self.generator(message, recent)
            except Exception:
                warning = "AI 해석이 잠시 어려워 질문의 키워드로 검색했어요."
        fallback = self._parse(message, recent)
        intent = generated or fallback
        return SearchIntent(
            region="부산",
            district=district or intent.district or fallback.district,
            category=category or intent.category or fallback.category,
            keyword=quick_keyword or intent.keyword or fallback.keyword,
        ), warning

    @staticmethod
    def _parse(message: str, recent: Sequence[SearchIntent]) -> SearchIntent:
        previous = recent[-1] if recent else SearchIntent()
        district = next((name for name in DISTRICTS if name in message), previous.district)
        category: PlaceCategory = previous.category
        if category == "all":
            category = "all"
        for candidate, words in CATEGORY_KEYWORDS.items():
            if any(word in message for word in words):
                category = candidate
                break
        keyword_parts = [word for word in ("돼지국밥", "밀면", "해산물", "고기", "회", "브런치", "오션뷰", "야경") if word in message]
        keyword = " ".join(keyword_parts) or previous.keyword or message.strip()
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
    response = genai.Client(api_key=settings.gemini_api_key).models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=SearchIntent.model_json_schema(),
            temperature=0.1,
        ),
    )
    return SearchIntent.model_validate_json(response.text or "{}")
