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
    template = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body,#map{width:100%;height:100%;margin:0}#fallback{display:none;padding:20px;font-family:sans-serif}.info{padding:10px;max-width:240px;font:13px sans-serif}.info b{display:block;margin-bottom:6px;color:#073b4c}</style></head>
<body><div id="map"></div><div id="fallback">지도를 불러오지 못했습니다. 아래 장소 카드를 이용해 주세요.</div><script>
const places=__PLACES__;
const SDK_URL="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false";
const SDK_TIMEOUT_MS=8000;
const LAYOUT_TIMEOUT_MS=5000;
const MAX_INIT_ATTEMPTS=2;
const mapElement=document.getElementById("map");
const fallbackElement=document.getElementById("fallback");

function fallback(){
  mapElement.style.display="none";
  fallbackElement.style.display="block";
}

function waitForLayout(){
  return new Promise((resolve,reject)=>{
    const started=Date.now();
    const check=()=>{
      const rect=mapElement.getBoundingClientRect();
      if(rect.width>0&&rect.height>0){resolve();return;}
      if(Date.now()-started>=LAYOUT_TIMEOUT_MS){reject(new Error("map layout timeout"));return;}
      requestAnimationFrame(check);
    };
    check();
  });
}

function loadSdk(){
  if(window.kakao&&window.kakao.maps)return Promise.resolve();
  return new Promise((resolve,reject)=>{
    const script=document.createElement("script");
    let settled=false;
    const finish=(callback,value)=>{
      if(settled)return;
      settled=true;
      clearTimeout(timer);
      callback(value);
    };
    script.dataset.kakaoSdk="true";
    script.src=SDK_URL;
    script.async=true;
    script.referrerPolicy="origin";
    script.onload=()=>{
      if(window.kakao&&window.kakao.maps)finish(resolve);
      else finish(reject,new Error("Kakao SDK unavailable"));
    };
    script.onerror=()=>finish(reject,new Error("Kakao SDK load failed"));
    const timer=setTimeout(()=>finish(reject,new Error("Kakao SDK timeout")),SDK_TIMEOUT_MS);
    document.head.appendChild(script);
  });
}

function createMap(){
  return new Promise((resolve,reject)=>{
    try{
      window.kakao.maps.load(()=>{
        try{
          const map=new window.kakao.maps.Map(mapElement,{center:new window.kakao.maps.LatLng(35.1796,129.0756),level:8});
          const bounds=new window.kakao.maps.LatLngBounds();
          places.forEach((p)=>{
            const pos=new window.kakao.maps.LatLng(p.latitude,p.longitude);
            const marker=new window.kakao.maps.Marker({map,position:pos,title:p.name});
            bounds.extend(pos);
            window.kakao.maps.event.addListener(marker,"click",()=>{
              const root=document.createElement("div");
              root.className="info";
              const title=document.createElement("b");
              title.textContent=p.name;
              root.appendChild(title);
              const addr=document.createElement("span");
              addr.textContent=p.address;
              root.appendChild(addr);
              if(p.url){
                const link=document.createElement("a");
                link.href=p.url;
                link.target="_blank";
                link.rel="noopener noreferrer";
                link.textContent=" 카카오맵 보기";
                root.appendChild(link);
              }
              new window.kakao.maps.InfoWindow({content:root,removable:true}).open(map,marker);
            });
          });
          let resizeFrame=0;
          const relayout=()=>{
            if(resizeFrame)cancelAnimationFrame(resizeFrame);
            resizeFrame=requestAnimationFrame(()=>{
              map.relayout();
              if(places.length)map.setBounds(bounds);
            });
          };
          const observer=new ResizeObserver(relayout);
          observer.observe(mapElement);
          relayout();
          resolve();
        }catch(error){reject(error);}
      });
    }catch(error){reject(error);}
  });
}

async function initialize(){
  await loadSdk();
  await waitForLayout();
  await createMap();
}

async function boot(){
  for(let attempt=0;attempt<MAX_INIT_ATTEMPTS;attempt+=1){
    try{await initialize();return;}
    catch(error){
      const failedScript=document.querySelector('script[data-kakao-sdk="true"]');
      if(failedScript&&!(window.kakao&&window.kakao.maps))failedScript.remove();
      if(attempt+1<MAX_INIT_ATTEMPTS)await new Promise((resolve)=>setTimeout(resolve,300));
    }
  }
  fallback();
}

boot();
</script></body></html>"""
    return template.replace("__PLACES__", places_json).replace("__KEY__", javascript_key)


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
