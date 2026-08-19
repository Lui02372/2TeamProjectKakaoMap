import json

import httpx

from app.config import settings
from app.schemas_food import FoodPlace


class ProviderCallError(Exception):
    pass


def get_mock_foods(food_count: int) -> list[FoodPlace]:
    mock_foods = [
        FoodPlace(
            id="mock-food-1",
            name="부산 해산물 식당",
            category_name="음식점 > 해물,생선",
            description="해운대 일정 근처에서 신선한 해산물을 즐기기 좋습니다.",
            address="부산 해운대구 우동",
            road_address="부산 해운대구 해운대해변로 264",
            latitude=35.1587,
            longitude=129.1604,
            phone="",
            kakao_place_url="",
            day=1,
            order=2,
        ),
        FoodPlace(
            id="mock-food-2",
            name="부산 돼지국밥",
            category_name="음식점 > 한식",
            description="부산을 대표하는 지역 음식을 맛보기 좋습니다.",
            address="부산 중구 부평동",
            road_address="부산 중구 광복로 00",
            latitude=35.1013,
            longitude=129.0301,
            phone="",
            kakao_place_url="",
            day=2,
            order=1,
        ),
        FoodPlace(
            id="mock-food-3",
            name="광안리 밀면",
            category_name="음식점 > 한식",
            description="광안리 해변 일정과 함께 가볍게 즐기기 좋습니다.",
            address="부산 수영구 광안동",
            road_address="부산 수영구 광안해변로 00",
            latitude=35.1531,
            longitude=129.1186,
            phone="",
            kakao_place_url="",
            day=2,
            order=2,
        ),
        FoodPlace(
            id="mock-food-4",
            name="자갈치 시장 회센터",
            category_name="음식점 > 해물,생선",
            description="부산의 해산물 분위기를 경험하기 좋은 장소입니다.",
            address="부산 중구 남포동",
            road_address="부산 중구 자갈치해안로 52",
            latitude=35.0969,
            longitude=129.0302,
            phone="",
            kakao_place_url="",
            day=3,
            order=1,
        ),
    ]

    return mock_foods[:food_count]


def _make_prompt(message: str, candidates: list[FoodPlace], food_count: int) -> str:
    candidate_text = "\n".join(
        f"- id: {food.id}, name: {food.name}, category: {food.category_name}"
        for food in candidates
    )

    return f"""
사용자의 여행 요청에 맞는 음식점을 후보 중에서 선택하세요.

사용자 요청:
{message}

후보 음식점:
{candidate_text}

반드시 아래 JSON 형식만 반환하세요.
{{
  "foods": [
    {{
      "id": "후보에 있는 id",
      "description": "추천 이유",
      "day": 1,
      "order": 1
    }}
  ]
}}

규칙:
- 후보에 없는 id를 만들지 마세요.
- 최대 {food_count}개만 선택하세요.
- day는 1부터 3 사이의 정수입니다.
- order는 해당 일차의 방문 순서입니다.
"""


def _merge_selected_foods(
    llm_text: str,
    candidates: list[FoodPlace],
    food_count: int,
) -> list[FoodPlace]:
    try:
        selected_data = json.loads(llm_text)
    except json.JSONDecodeError as exc:
        raise ProviderCallError("LLM이 올바른 JSON을 반환하지 않았습니다.") from exc

    candidate_by_id = {food.id: food for food in candidates}
    foods: list[FoodPlace] = []
    used_ids: set[str] = set()

    for item in selected_data.get("foods", []):
        food_id = str(item.get("id", ""))

        if food_id not in candidate_by_id or food_id in used_ids:
            continue

        used_ids.add(food_id)

        day = max(1, min(3, int(item.get("day", 1))))
        order = max(1, int(item.get("order", 1)))
        description = str(item.get("description", "추천 음식점입니다."))

        foods.append(
            candidate_by_id[food_id].model_copy(
                update={
                    "description": description,
                    "day": day,
                    "order": order,
                }
            )
        )

    return foods[:food_count]


def get_gemini_foods(message: str, food_count: int) -> list[FoodPlace]:
    if not settings.gemini_api_key:
        raise ProviderCallError("GEMINI_API_KEY가 설정되지 않았습니다.")

    candidates = get_mock_foods(10)
    prompt = _make_prompt(message, candidates, food_count)

    try:
        response = httpx.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{settings.gemini_model}:generateContent"
            ),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        llm_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise ProviderCallError("Gemini 호출에 실패했습니다.") from exc

    return _merge_selected_foods(llm_text, candidates, food_count)


def get_openai_foods(message: str, food_count: int) -> list[FoodPlace]:
    if not settings.openai_api_key:
        raise ProviderCallError("OPENAI_API_KEY가 설정되지 않았습니다.")

    candidates = get_mock_foods(10)
    prompt = _make_prompt(message, candidates, food_count)

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
            timeout=30,
        )
        response.raise_for_status()
        llm_text = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise ProviderCallError("OpenAI 호출에 실패했습니다.") from exc

    return _merge_selected_foods(llm_text, candidates, food_count)


def get_ollama_foods(message: str, food_count: int) -> list[FoodPlace]:
    candidates = get_mock_foods(10)
    prompt = _make_prompt(message, candidates, food_count)

    try:
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=60,
        )
        response.raise_for_status()
        llm_text = response.json()["message"]["content"]
    except (httpx.HTTPError, KeyError) as exc:
        raise ProviderCallError("Ollama 호출에 실패했습니다. Ollama 서버와 모델을 확인하세요.") from exc

    return _merge_selected_foods(llm_text, candidates, food_count)
