"""Kakao Maps JavaScript SDK용 안전한 HTML 컴포넌트."""

import json
import re

import streamlit as st
import streamlit.components.v1 as components

from models.travel import TravelPlace


_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _serialize_places(places: list[TravelPlace]) -> str:
    payload = [
        {
            "name": place.name,
            "type": place.place_type,
            "typeLabel": "랜드마크" if place.place_type == "landmark" else "음식점",
            "description": place.description,
            "address": place.road_address or place.address,
            "latitude": place.latitude,
            "longitude": place.longitude,
            "day": place.day,
            "order": place.order,
            "url": place.safe_kakao_url,
        }
        for place in places
        if place.has_valid_coordinates
    ]
    # script 태그 종료 문자열과 HTML 토큰이 데이터에서 실행되지 않도록 이스케이프한다.
    return json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")


def generate_kakao_map_html(places: list[TravelPlace], javascript_key: str) -> str:
    if not javascript_key or not _KEY_PATTERN.fullmatch(javascript_key):
        raise ValueError("올바른 Kakao JavaScript Key가 필요합니다.")

    places_json = _serialize_places(places)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    html, body, #map {{ width: 100%; height: 100%; margin: 0; }}
    #fallback {{ display:none; padding:16px; font-family:sans-serif; color:#842029; }}
    .info {{ max-width:250px; padding:10px; font:13px/1.45 sans-serif; }}
    .info strong {{ display:block; margin-bottom:5px; font-size:14px; }}
    .info a {{ display:inline-block; margin-top:6px; color:#075985; }}
  </style>
  <script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={javascript_key}&autoload=false"></script>
</head>
<body>
  <div id="map" aria-label="여행 장소 지도"></div>
  <div id="fallback">지도를 불러오지 못했습니다. 아래 장소 카드와 Kakao 링크를 이용해 주세요.</div>
  <script>
    const places = {places_json};
    const showFallback = () => {{
      document.getElementById('map').style.display = 'none';
      document.getElementById('fallback').style.display = 'block';
    }};
    const addText = (root, tag, value) => {{
      if (!value) return;
      const node = document.createElement(tag);
      node.textContent = value;
      root.appendChild(node);
    }};
    try {{
      if (!window.kakao || !window.kakao.maps) throw new Error('sdk');
      kakao.maps.load(() => {{
        try {{
          const map = new kakao.maps.Map(document.getElementById('map'), {{
            center: new kakao.maps.LatLng(37.5665, 126.9780), level: 7
          }});
          const bounds = new kakao.maps.LatLngBounds();
          const infoWindow = new kakao.maps.InfoWindow({{ removable: true }});
          places.forEach((place) => {{
            const position = new kakao.maps.LatLng(place.latitude, place.longitude);
            const color = place.type === 'landmark' ? '2563eb' : 'dc2626';
            const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="42"><path fill="#${{color}}" stroke="white" stroke-width="2" d="M15 1C7.3 1 1 7.3 1 15c0 10 14 26 14 26s14-16 14-26C29 7.3 22.7 1 15 1z"/><circle cx="15" cy="15" r="5" fill="white"/></svg>`;
            const image = new kakao.maps.MarkerImage(
              'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
              new kakao.maps.Size(30, 42)
            );
            const marker = new kakao.maps.Marker({{ map, position, image, title: place.name }});
            bounds.extend(position);
            kakao.maps.event.addListener(marker, 'click', () => {{
              const content = document.createElement('div');
              content.className = 'info';
              addText(content, 'strong', place.name);
              addText(content, 'span', `${{place.typeLabel}} · ${{place.day}}일차 ${{place.order}}번째`);
              addText(content, 'p', place.description);
              addText(content, 'p', place.address);
              if (place.url) {{
                const link = document.createElement('a');
                link.href = place.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
                link.textContent = 'Kakao 장소 상세 보기'; content.appendChild(link);
              }}
              infoWindow.setContent(content); infoWindow.open(map, marker);
            }});
          }});
          if (places.length === 1) {{ map.setCenter(bounds.getSouthWest()); map.setLevel(4); }}
          else {{ map.setBounds(bounds); }}
        }} catch (_) {{ showFallback(); }}
      }});
    }} catch (_) {{ showFallback(); }}
  </script>
</body>
</html>"""


def render_kakao_map(places: list[TravelPlace], javascript_key: str) -> None:
    mappable = [place for place in places if place.has_valid_coordinates]
    if not mappable:
        st.info("지도에 표시할 유효한 좌표가 없습니다.")
        return
    if not javascript_key:
        st.info("지도를 보려면 `.env`에 `KAKAO_JAVASCRIPT_KEY`를 설정해 주세요.")
        return
    try:
        html = generate_kakao_map_html(mappable, javascript_key)
    except ValueError:
        st.warning("Kakao JavaScript Key 형식이 올바르지 않아 지도를 표시하지 않습니다.")
        return
    components.html(html, height=560, scrolling=False)
