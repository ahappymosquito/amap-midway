"""携程酒店房型查询。

本文件用携程公开联想接口匹配酒店，再读取该店点评侧房型筛选列表作为一级床型；不展示房价。在售报价接口有反爬，拿不到实时空房。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.hotel_filters import classify_bed_types
from app.open_links import CTRIP_CITY_IDS
from app.schemas import Place

SEARCH_URL = "https://m.ctrip.com/restapi/soa2/21881/json/gaHotelSearchEngine"
COMMENT_URL = "https://m.ctrip.com/restapi/soa2/14605/getHotelComment"
CTRIP_ROOM_LIMIT = 24
CTRIP_CONCURRENCY = 6
REQUEST_TIMEOUT = 8.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://m.ctrip.com",
    "Referer": "https://m.ctrip.com/webapp/hotel/",
    "Accept": "application/json",
    "x-ctx-group": "ctrip",
    "x-ctx-locale": "zh-CN",
    "x-ctx-currency": "CNY",
}

_cache: dict[str, tuple[list[str], list[str]]] = {}


async def attach_ctrip_bed_types(places: list[Place], city: str) -> None:
    """为靠前的酒店补上携程该店房型和一级床型标签。"""

    targets = [place for place in places if place.category == "hotel"][:CTRIP_ROOM_LIMIT]
    if not targets:
        return
    city_id = CTRIP_CITY_IDS.get((city or "").replace("市", "") or "北京", 1)
    semaphore = asyncio.Semaphore(CTRIP_CONCURRENCY)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:

        async def fill(place: Place) -> None:
            async with semaphore:
                rooms, beds = await lookup_hotel_rooms(client, place.name, city_id)
            place.sale_rooms = rooms
            place.bed_types = beds

        await asyncio.gather(*(fill(place) for place in targets))


async def lookup_hotel_rooms(
    client: httpx.AsyncClient,
    name: str,
    city_id: int,
) -> tuple[list[str], list[str]]:
    """按店名查询携程房型列表，失败时返回空。"""

    key = f"{city_id}|{name}"
    cached = _cache.get(key)
    if cached is not None:
        return cached
    rooms: list[str] = []
    try:
        hotel_id = await _search_hotel_id(client, name, city_id)
        if hotel_id:
            rooms = await _fetch_room_names(client, hotel_id)
    except (httpx.HTTPError, ValueError, TypeError):
        rooms = []
    beds = classify_bed_types(rooms)
    result = (rooms[:6], beds)
    if len(_cache) > 300:
        _cache.clear()
    _cache[key] = result
    return result


async def _search_hotel_id(client: httpx.AsyncClient, name: str, city_id: int) -> str:
    payload = {
        "keyword": name,
        "searchType": "H",
        "platform": "online",
        "pageID": "102001",
        "head": {
            "Locale": "zh-CN",
            "Currency": "CNY",
            "PageId": "102001",
            "group": "ctrip",
            "HotelExtension": {"group": "CTRIP", "WebpSupport": False},
        },
    }
    response = await client.post(SEARCH_URL, json=payload)
    response.raise_for_status()
    data = response.json()
    results = ((data.get("Response") or {}).get("searchResults")) or []
    matched = _best_match(results, name, city_id)
    if not matched:
        return ""
    return str(matched.get("id") or "")


async def _fetch_room_names(client: httpx.AsyncClient, hotel_id: str) -> list[str]:
    payload = {
        "hotelID": int(hotel_id) if str(hotel_id).isdigit() else hotel_id,
        "pageIndex": 1,
        "pageSize": 1,
        "head": {"cid": "09031069217559688465", "syscode": "30", "lang": "01", "cver": "1.0"},
    }
    response = await client.post(COMMENT_URL, json=payload)
    response.raise_for_status()
    data = response.json()
    names = [str(item) for item in (data.get("roomFilterList") or []) if str(item).strip()]
    if names:
        return names
    basic = data.get("basicRoomFilterList") or []
    return [str(item.get("name") or "").strip() for item in basic if isinstance(item, dict) and item.get("name")]


def _best_match(results: list[Any], name: str, city_id: int) -> dict[str, Any] | None:
    hotels = [item for item in results if isinstance(item, dict) and str(item.get("type") or "").lower() == "hotel"]
    if not hotels:
        hotels = [item for item in results if isinstance(item, dict)]
    same_city = [item for item in hotels if int(item.get("cityId") or 0) == city_id] or hotels
    for item in same_city:
        if str(item.get("word") or "") == name:
            return item
    for item in same_city:
        if _names_close(name, str(item.get("word") or "")):
            return item
    return None


def _names_close(amap_name: str, ctrip_name: str) -> bool:
    left = amap_name.replace(" ", "")
    right = ctrip_name.replace(" ", "")
    if len(left) >= 8 and len(right) >= 8 and (left in right or right in left):
        return True
    overlap = _token_overlap(_significant_tokens(amap_name), _significant_tokens(ctrip_name))
    if overlap >= 2:
        return True
    return False


def _token_overlap(left: set[str], right: set[str]) -> int:
    used: set[str] = set()
    count = 0
    for token in left:
        for other in right:
            if other in used:
                continue
            if token == other or (len(token) >= 2 and len(other) >= 2 and (token in other or other in token)):
                used.add(other)
                count += 1
                break
    return count


def _significant_tokens(name: str) -> set[str]:
    cleaned = name
    for sep in "()（）[]【】·-/ ":
        cleaned = cleaned.replace(sep, " ")
    stop = {"北京", "上海", "广州", "深圳", "杭州", "成都", "酒店", "饭店", "宾馆", "中国", "店"}
    tokens: set[str] = set()
    for part in cleaned.split():
        if part.endswith("店") and len(part) > 2:
            part = part[:-1]
        if len(part) >= 2 and part not in stop:
            tokens.add(part)
    return tokens
