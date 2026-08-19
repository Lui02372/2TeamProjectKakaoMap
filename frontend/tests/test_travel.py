import pytest
from pydantic import ValidationError

from components.kakao_map import generate_kakao_map_html
from clients import travel_client
from models.travel import (
    ProviderTravelResult,
    TravelCompareResponse,
    TravelPlace,
    TravelPlanContent,
    build_compare_payload,
    filter_places,
)


def place(**overrides):
    data = {
        "id": "1",
        "name": "해운대해수욕장",
        "place_type": "landmark",
        "description": "대표 해변",
        "latitude": 35.1587,
        "longitude": 129.1604,
        "kakao_place_url": "https://place.map.kakao.com/1",
        "day": 1,
        "order": 1,
    }
    data.update(overrides)
    return TravelPlace.model_validate(data)


def content(**overrides):
    data = {
        "destination": "부산",
        "summary": "바다 여행",
        "nights": 1,
        "days": 2,
        "landmarks": [place()],
        "foods": [],
    }
    data.update(overrides)
    return TravelPlanContent.model_validate(data)


def test_payload_trims_deduplicates_and_casts_counts():
    assert build_compare_payload(" 부산 여행 ", ["mock", "mock", "openai"], 6.0, 4) == {
        "message": "부산 여행",
        "providers": ["mock", "openai"],
        "landmark_count": 6,
        "food_count": 4,
    }


@pytest.mark.parametrize(
    "message,providers,landmark_count,food_count",
    [("  ", ["mock"], 6, 4), ("여행", [], 6, 4), ("여행", ["mock"], 0, 4)],
)
def test_invalid_payload_is_rejected(message, providers, landmark_count, food_count):
    with pytest.raises(ValueError):
        build_compare_payload(message, providers, landmark_count, food_count)


def test_kakao_x_y_are_mapped_and_invalid_coordinates_are_tolerated():
    mapped = place(latitude=None, longitude=None, x="129.1", y="35.1")
    assert mapped.longitude == 129.1
    assert mapped.latitude == 35.1
    assert mapped.has_valid_coordinates
    assert not place(latitude="wrong", longitude=500).has_valid_coordinates


def test_places_are_deduplicated_sorted_and_filtered():
    first = place(id="same", day=2, order=1)
    duplicate = place(id="same", name="중복", day=1)
    food = place(id="2", name="식당", place_type="food", day=1, order=2)
    plan = content(landmarks=[first, duplicate], foods=[food])
    places = plan.normalized_places()
    assert [item.id for item in places] == ["2", "same"]
    assert filter_places(places, 1, "food") == [food]


def test_status_contract_and_partial_success_response():
    success = ProviderTravelResult(provider="mock", status="success", content=content())
    failure = ProviderTravelResult(provider="openai", status="error", error="실패")
    response = TravelCompareResponse(
        request_count=2,
        landmark_count=6,
        food_count=4,
        results=[success, failure],
    )
    assert response.successful_results == [success]
    with pytest.raises(ValidationError):
        ProviderTravelResult(provider="mock", status="success")


def test_unsafe_url_is_removed_and_html_data_cannot_close_script():
    malicious = place(
        name="</script><script>alert(1)</script>",
        kakao_place_url="javascript:alert(1)",
    )
    assert malicious.safe_kakao_url == ""
    html = generate_kakao_map_html([malicious], "validKey_123")
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html
    assert "javascript:alert(1)" not in html


def test_trip_day_contract_is_checked():
    with pytest.raises(ValidationError):
        content(nights=2, days=2)
    with pytest.raises(ValidationError):
        content(landmarks=[place(day=3)])


def test_client_sends_all_providers_in_one_request(monkeypatch):
    calls = []

    def fake_request(method, path, json):
        calls.append((method, path, json))
        return {
            "request_count": 2,
            "landmark_count": 6,
            "food_count": 4,
            "results": [
                {
                    "provider": "mock",
                    "status": "success",
                    "content": content().model_dump(mode="json"),
                },
                {"provider": "openai", "status": "error", "error": "실패"},
            ],
        }

    monkeypatch.setattr(travel_client, "request", fake_request)
    response = travel_client.compare_travel_plans(
        "부산 여행", ["mock", "openai"], 6, 4
    )

    assert response.request_count == 2
    assert len(calls) == 1
    assert calls[0][0:2] == ("POST", "/api/travel-plans/compare")
    assert calls[0][2]["providers"] == ["mock", "openai"]
