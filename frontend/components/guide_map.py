import json
import re

import streamlit as st
import streamlit.components.v1 as components

from models.guide import GuidePlace


_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _serialize_places(places: list[GuidePlace]) -> str:
    payload = [{
        "name": place.name, "address": place.road_address or place.address,
        "latitude": place.latitude, "longitude": place.longitude, "url": place.safe_kakao_url,
    } for place in places if -90 <= place.latitude <= 90 and -180 <= place.longitude <= 180]
    return json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")


def generate_kakao_map_html(places: list[GuidePlace], javascript_key: str) -> str:
    if not javascript_key or not _KEY_PATTERN.fullmatch(javascript_key):
        raise ValueError("올바른 Kakao JavaScript Key가 필요합니다.")
    places_json = _serialize_places(places)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body,#map{{width:100%;height:100%;margin:0}}#fallback{{display:none;padding:20px;font-family:sans-serif}}.info{{padding:10px;max-width:240px;font:13px sans-serif}}.info b{{display:block;margin-bottom:6px;color:#073b4c}}</style>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={javascript_key}&autoload=false"></script></head>
<body><div id="map"></div><div id="fallback">지도를 불러오지 못했습니다. 아래 장소 카드를 이용해 주세요.</div><script>
const places={places_json}; const fallback=()=>{{document.getElementById('map').style.display='none';document.getElementById('fallback').style.display='block'}};
try{{kakao.maps.load(()=>{{const map=new kakao.maps.Map(document.getElementById('map'),{{center:new kakao.maps.LatLng(35.1796,129.0756),level:8}});const bounds=new kakao.maps.LatLngBounds();
places.forEach((p,i)=>{{const pos=new kakao.maps.LatLng(p.latitude,p.longitude);const marker=new kakao.maps.Marker({{map,position:pos,title:p.name}});bounds.extend(pos);kakao.maps.event.addListener(marker,'click',()=>{{const root=document.createElement('div');root.className='info';const title=document.createElement('b');title.textContent=p.name;root.appendChild(title);const addr=document.createElement('span');addr.textContent=p.address;root.appendChild(addr);if(p.url){{const a=document.createElement('a');a.href=p.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=' 카카오맵 보기';root.appendChild(a)}}new kakao.maps.InfoWindow({{content:root,removable:true}}).open(map,marker)}})}});if(places.length)map.setBounds(bounds)}})}}catch(e){{fallback()}}
</script></body></html>"""


def render_kakao_map(places: list[GuidePlace], javascript_key: str) -> None:
    if not places:
        st.info("검색 결과가 지도에 표시됩니다.")
        return
    if not javascript_key:
        st.info("지도 키가 설정되지 않았습니다. 장소 카카오맵 링크는 계속 이용할 수 있어요.")
        return
    try:
        components.html(generate_kakao_map_html(places, javascript_key), height=520, scrolling=False)
    except ValueError:
        st.warning("지도 키 형식을 확인해 주세요.")
