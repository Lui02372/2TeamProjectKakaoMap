from time import perf_counter

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.providers_food import (
    ProviderCallError,
    get_gemini_foods,
    get_mock_foods,
    get_ollama_foods,
    get_openai_foods,
)
from app.schemas_food import TravelPlanGenerateRequest


router = APIRouter(tags=["Food"])
agent_router = router
structured_output_router = APIRouter()


@router.post("/api/travel-plans/generate")
def generate_travel_plan(request: TravelPlanGenerateRequest):
    started_at = perf_counter()

    try:
        if request.provider == "mock":
            foods = get_mock_foods(request.food_count)
            model = "mock-provider"

        elif request.provider == "gemini":
            foods = get_gemini_foods(request.message, request.food_count)
            model = settings.gemini_model

        elif request.provider == "openai":
            foods = get_openai_foods(request.message, request.food_count)
            model = settings.openai_model

        elif request.provider == "ollama":
            foods = get_ollama_foods(request.message, request.food_count)
            model = settings.ollama_model

        else:
            raise HTTPException(
                status_code=400,
                detail="지원하는 provider는 mock, gemini, openai, ollama입니다.",
            )

    except ProviderCallError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    latency_ms = int((perf_counter() - started_at) * 1000)

    return {
        "provider": request.provider,
        "model": model,
        "latency_ms": latency_ms,
        "content": {
            "destination": "부산",
            "summary": "음식 취향을 반영한 부산 여행 음식점 추천입니다.",
            "nights": 2,
            "days": 3,
            "landmarks": [],
            "foods": foods,
        },
        "warnings": [],
    }
