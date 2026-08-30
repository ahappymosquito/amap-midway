"""多点选址业务模块。

本文件根据多个通勤点搜索中间区域的餐馆或酒店，按真实地铁时长排序，并为餐馆叠加扫街榜状元/烟火小店/甄选可视化。
"""

import asyncio

from fastapi import HTTPException, status

from app.amap_client import AmapClient
from app.budget import couple_budget, is_over_budget
from app.distance import centroid, haversine_distance_m, search_radius_from_points
from app.metro import parse_all_transit_plans, parse_riding_payload, select_metro_stations, to_metro_station
from app.open_links import amap_ranking_url, build_open_links
from app.schemas import (
    CommuteTimes,
    LocationResponse,
    MetroStation,
    OriginInput,
    OriginRoutes,
    Place,
    PlaceCategory,
    PlacesSearchResponse,
    PoiRecord,
)

TRANSIT_RANK_LIMIT = 8
TRANSIT_CONCURRENCY = 6
PREPLAN_COUNT = 3
BOARD_CHAMPION_KEYWORD = "状元榜"
BOARD_STREET_KEYWORD = "烟火小店"
BOARD_SELECT_KEYWORD = "品质甄选"


async def search_places_between(
    client: AmapClient,
    origins: list[OriginInput],
    category: PlaceCategory,
    budget_per_person: int,
    people_count: int,
    city: str = "",
) -> PlacesSearchResponse:
    """搜索多个通勤点之间的餐馆或酒店候选。城市由第一个可解析地名推断。"""

    if len(origins) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="至少填写两个地点。")

    points, city = await _resolve_origins(client, origins, city)

    coords = [(item.lng, item.lat) for item in points]
    mid_lng, mid_lat = centroid(coords)
    radius = search_radius_from_points(coords)
    around_task = client.search_around_pois(mid_lng, mid_lat, radius, category)
    if category == "restaurant":
        around, champion_records, street_records, select_records = await asyncio.gather(
            around_task,
            client.search_text_pois(BOARD_CHAMPION_KEYWORD, city),
            client.search_text_pois(BOARD_STREET_KEYWORD, city),
            client.search_text_pois(BOARD_SELECT_KEYWORD, city),
        )
    else:
        around = await around_task
        champion_records, street_records, select_records = [], [], []
    max_distance = int(radius * 1.3)
    champion_ids = {
        item.id
        for item in champion_records
        if haversine_distance_m(mid_lng, mid_lat, item.lng, item.lat) <= max_distance
    }
    street_ids = {
        item.id
        for item in street_records
        if haversine_distance_m(mid_lng, mid_lat, item.lng, item.lat) <= max_distance
    } - champion_ids
    select_ids = {
        item.id
        for item in select_records
        if haversine_distance_m(mid_lng, mid_lat, item.lng, item.lat) <= max_distance
    } - champion_ids - street_ids
    records = [
        record
        for record in around
        if haversine_distance_m(mid_lng, mid_lat, record.lng, record.lat) <= max_distance
    ]
    seen_ids = {item.id for item in records}
    for extra in [*champion_records, *street_records, *select_records]:
        if extra.id in seen_ids:
            continue
        if haversine_distance_m(mid_lng, mid_lat, extra.lng, extra.lat) > max_distance:
            continue
        records.append(extra)
        seen_ids.add(extra.id)
    records.sort(
        key=lambda record: max(haversine_distance_m(point.lng, point.lat, record.lng, record.lat) for point in points)
    )
    commute_pack, metro_stations = await asyncio.gather(
        _metro_and_ride_times(client, points, records[:TRANSIT_RANK_LIMIT], city),
        _metro_stations_between(client, points, (mid_lng, mid_lat), radius),
    )
    commute_by_id, payload_by_id = commute_pack

    places: list[Place] = []
    for record in records:
        commutes = commute_by_id.get(record.id) or [CommuteTimes() for _ in points]
        farthest = max(haversine_distance_m(point.lng, point.lat, record.lng, record.lat) for point in points)
        places.append(
            Place(
                id=record.id,
                name=record.name,
                lng=record.lng,
                lat=record.lat,
                address=record.address,
                category=category,
                rating=record.rating,
                cost=record.cost,
                commutes=commutes,
                fairness_s=_fairness_seconds(commutes, farthest),
                over_budget=is_over_budget(category, record.cost, budget_per_person, people_count),
                budget_unknown=record.cost is None,
                open_links=build_open_links(
                    name=record.name,
                    lng=record.lng,
                    lat=record.lat,
                    category=category,
                    poi_id=record.id,
                    city=city,
                ),
                board=_board_tag(record.id, champion_ids, street_ids, select_ids, record.tag),
            )
        )

    places.sort(key=lambda item: (item.over_budget, item.fairness_s, item.name))
    for place in places[:PREPLAN_COUNT]:
        place.origin_routes = _origin_routes_from_payloads(payload_by_id.get(place.id), len(points))
    return PlacesSearchResponse(
        origins=points,
        midpoint_lng=mid_lng,
        midpoint_lat=mid_lat,
        radius_m=radius,
        category=category,
        people_count=people_count,
        budget_per_person=budget_per_person,
        budget_total=couple_budget(budget_per_person, people_count),
        places=places,
        metro_stations=metro_stations,
        metro_lines=[],
        amap_ranking_url=amap_ranking_url(city, "hotel" if category == "hotel" else "food"),
    )


async def _resolve_origins(
    client: AmapClient,
    origins: list[OriginInput],
    city_hint: str = "",
) -> tuple[list[LocationResponse], str]:
    """依次解析地点，用先解析出的城市约束后续地点。"""

    points: list[LocationResponse] = []
    city = city_hint.strip()
    for index, origin in enumerate(origins):
        label = f"地点 {chr(ord('A') + index)}"
        located = await resolve_origin(client, origin, label, city)
        if not located.city:
            located.city = await client.reverse_city(located.lng, located.lat)
        if located.city and not city:
            city = located.city
        elif city and not located.city:
            located.city = city
        points.append(located)
    return points, city or "北京"


async def resolve_origin(client: AmapClient, origin: OriginInput, label: str, city: str = "") -> LocationResponse:
    """把地址或坐标解析为统一的地点信息。"""

    if origin.lng is not None and origin.lat is not None:
        address = (origin.address or "").strip() or label
        return LocationResponse(lng=origin.lng, lat=origin.lat, formatted_address=address, city=city)
    address = (origin.address or "").strip()
    if not address:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{label} 请填写地址或经纬度。")
    return await client.geocode(address, city=city)


async def _metro_and_ride_times(
    client: AmapClient,
    points: list[LocationResponse],
    records: list[PoiRecord],
    city: str,
) -> tuple[dict[str, list[CommuteTimes]], dict[str, list[tuple[dict | None, dict | None]]]]:
    """对优先候选计算每个通勤点的地铁和骑行时长，并保留规划原文供前几名预规划。"""

    result: dict[str, list[CommuteTimes]] = {
        record.id: [CommuteTimes() for _ in points] for record in records
    }
    payloads: dict[str, list[tuple[dict | None, dict | None]]] = {
        record.id: [(None, None) for _ in points] for record in records
    }
    if not records:
        return result, payloads

    semaphore = asyncio.Semaphore(TRANSIT_CONCURRENCY)

    async def fill(record: PoiRecord, origin_index: int, point: LocationResponse) -> None:
        async with semaphore:
            transit_payload, riding_payload = await asyncio.gather(
                client.transit_payload((point.lng, point.lat), (record.lng, record.lat), city),
                client.riding_payload((point.lng, point.lat), (record.lng, record.lat)),
            )
        plans = parse_all_transit_plans(transit_payload)
        riding_s, _path = parse_riding_payload(riding_payload)
        transit_s = plans[0].duration_s if plans else None
        result[record.id][origin_index] = CommuteTimes(transit_s=transit_s, riding_s=riding_s)
        payloads[record.id][origin_index] = (transit_payload, riding_payload)

    await asyncio.gather(
        *[fill(record, origin_index, point) for record in records for origin_index, point in enumerate(points)]
    )
    return result, payloads


def _origin_routes_from_payloads(
    payloads: list[tuple[dict | None, dict | None]] | None,
    origin_count: int,
) -> list[OriginRoutes]:
    """把搜索阶段缓存的规划原文转成前几名可用的多种出行方案。"""

    rows = payloads or [(None, None) for _ in range(origin_count)]
    routes: list[OriginRoutes] = []
    for transit_payload, riding_payload in rows:
        riding_s, riding_path = parse_riding_payload(riding_payload)
        routes.append(
            OriginRoutes(
                transit_plans=parse_all_transit_plans(transit_payload),
                riding_s=riding_s,
                riding_path=riding_path,
            )
        )
    return routes


async def _metro_stations_between(
    client: AmapClient,
    points: list[LocationResponse],
    center: tuple[float, float],
    radius: int,
) -> list[MetroStation]:
    """搜索通勤点之间的地铁站，作为地图参考标注。"""

    records = await client.search_metro_stations(center[0], center[1], radius)
    stations = [
        to_metro_station(record.id, record.name, record.lng, record.lat, record.address)
        for record in records
        if not record.typecode.startswith("150501")
    ]
    return select_metro_stations(stations, points, center)


def _board_tag(
    place_id: str,
    champion_ids: set[str],
    street_ids: set[str],
    select_ids: set[str],
    tag: str = "",
) -> str | None:
    """把扫街榜状元/烟火小店/甄选命中标到候选店上。"""

    text = tag or ""
    if place_id in champion_ids or "状元" in text or "必吃" in text:
        return "champion"
    if place_id in street_ids or "烟火" in text:
        return "street"
    if place_id in select_ids or "甄选" in text:
        return "select"
    return None


def _fairness_seconds(commutes: list[CommuteTimes], fallback_m: int) -> int:
    """用最慢一侧的地铁时间衡量公平性；没有地铁数据时退回骑行，再退回距离。"""

    transits = [item.transit_s for item in commutes]
    if transits and all(item is not None for item in transits):
        return max(item or 0 for item in transits)
    rides = [item.riding_s for item in commutes]
    if rides and all(item is not None for item in rides):
        return max(item or 0 for item in rides)
    return fallback_m
