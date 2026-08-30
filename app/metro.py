"""地铁线路与公交规划解析模块。

本文件从高德 POI 和公交/骑行规划结果中提取线路名、站点和折线坐标，供地图同线路同色标注使用。
"""

from __future__ import annotations

import re
from typing import Any

from app.distance import haversine_distance_m
from app.schemas import LocationResponse, MetroLine, MetroStation, RouteLeg, RoutePoint, RouteSegment, TransitPlan

LINE_RE = re.compile(
    r"(?:地铁)?"
    r"("
    r"首都机场线|大兴机场线|机场线|"
    r"亦庄线|房山线|昌平线|燕房线|西郊线|八通线|大兴线|"
    r"S1线|"
    r"\d+号线(?:支线)?"
    r")"
)
STATION_NAME_RE = re.compile(r"（地铁站）|\(地铁站\)|地铁站$")
BBOX_PAD_M = 900
METRO_STATION_LIMIT = 40
MAX_TRANSIT_PLANS = 3


def parse_line_names(*texts: str) -> list[str]:
    """从地址、站名或公交线路名中提取去重后的地铁线路名。"""

    names: list[str] = []
    for text in texts:
        for match in LINE_RE.finditer(text or ""):
            name = match.group(1)
            if name not in names:
                names.append(name)
    return names


def clean_station_name(name: str) -> str:
    """去掉高德地铁站 POI 名称里的“地铁站”后缀。"""

    return STATION_NAME_RE.sub("", name or "").strip() or (name or "地铁站")


def decode_polyline(text: str) -> list[tuple[float, float]]:
    """把高德 polyline 字符串解码为 (lng, lat) 列表。"""

    points: list[tuple[float, float]] = []
    if not text or isinstance(text, list):
        return points
    for part in str(text).split(";"):
        chunk = part.strip()
        if not chunk or "," not in chunk:
            continue
        lng_text, lat_text = chunk.split(",", maxsplit=1)
        try:
            points.append((float(lng_text), float(lat_text)))
        except ValueError:
            continue
    return points


def in_origins_bbox(lng: float, lat: float, points: list[LocationResponse], pad_m: int = BBOX_PAD_M) -> bool:
    """判断站点是否落在通勤点外包矩形（含余量）内，用作“两点之间”的参考范围。"""

    if not points:
        return False
    min_lng = min(item.lng for item in points)
    max_lng = max(item.lng for item in points)
    min_lat = min(item.lat for item in points)
    max_lat = max(item.lat for item in points)
    pad_deg = pad_m / 111_000
    return (min_lng - pad_deg) <= lng <= (max_lng + pad_deg) and (min_lat - pad_deg) <= lat <= (max_lat + pad_deg)


def to_metro_station(record_id: str, name: str, lng: float, lat: float, *line_sources: str) -> MetroStation:
    """把 POI 或公交站点整理为地铁站标注数据。"""

    return MetroStation(
        id=record_id or f"{lng},{lat}",
        name=clean_station_name(name),
        lng=lng,
        lat=lat,
        lines=parse_line_names(*line_sources, name),
    )


def select_metro_stations(
    stations: list[MetroStation],
    origins: list[LocationResponse],
    center: tuple[float, float],
) -> list[MetroStation]:
    """保留通勤点之间的地铁站，按离中心距离排序并限制数量。"""

    filtered = [item for item in stations if in_origins_bbox(item.lng, item.lat, origins)]
    filtered.sort(key=lambda item: haversine_distance_m(center[0], center[1], item.lng, item.lat))
    return filtered[:METRO_STATION_LIMIT]


def parse_transit_payload(payload: dict[str, Any] | None) -> tuple[int | None, list[RouteSegment]]:
    """解析高德公交一体化规划，得到最优方案时长和折线段。"""

    plans = parse_all_transit_plans(payload)
    if not plans:
        return None, []
    return plans[0].duration_s, plans[0].segments


def parse_all_transit_plans(payload: dict[str, Any] | None) -> list[TransitPlan]:
    """解析高德公交规划中的多条方案，最多保留三条。"""

    if not payload:
        return []
    transits = (payload.get("route") or {}).get("transits") or []
    plans: list[TransitPlan] = []
    for raw in transits[:MAX_TRANSIT_PLANS]:
        if not isinstance(raw, dict):
            continue
        duration, segments = _parse_one_transit(raw)
        if not segments:
            continue
        plan = TransitPlan(duration_s=duration, summary=plan_summary(segments), segments=segments)
        plans.append(fill_plan_stats(plan))
    plans.sort(key=lambda item: (0 if _has_metro(item) else 1, item.duration_s or 10**9))
    return plans


def _has_metro(plan: TransitPlan) -> bool:
    if "号线" in (plan.summary or "") or "机场线" in (plan.summary or ""):
        return True
    return any((segment.line or "") and (segment.mode or "").upper() != "BUS" for segment in plan.segments)


def fill_plan_stats(plan: TransitPlan) -> TransitPlan:
    """补齐走路、地铁、换乘时长和分段明细。"""

    walking = 0
    metro = 0
    transfer = 0
    transfer_count = 0
    legs: list[RouteLeg] = []
    total = len(plan.segments)
    for index, segment in enumerate(plan.segments):
        mode = (segment.mode or "").upper()
        duration = segment.duration_s
        amount = duration or 0
        if mode == "WALK":
            walking += amount
            prev_ride = any((plan.segments[item].mode or "").upper() != "WALK" for item in range(index))
            next_ride = any((plan.segments[item].mode or "").upper() != "WALK" for item in range(index + 1, total))
            if prev_ride and next_ride:
                transfer += amount
                transfer_count += 1
                label = "换乘步行"
            elif not prev_ride:
                label = "步行到站"
            else:
                label = "步行到店"
            legs.append(RouteLeg(label=label, mode="WALK", duration_s=duration))
        elif mode in {"SUBWAY", "METRO", "METRO_RAIL"}:
            metro += amount
            legs.append(RouteLeg(label=segment.line or "地铁", mode="SUBWAY", duration_s=duration))
        elif mode == "BUS":
            legs.append(RouteLeg(label=segment.line or "公交", mode="BUS", duration_s=duration))
        else:
            legs.append(RouteLeg(label=segment.line or mode or "其他", mode=mode, duration_s=duration))
    plan.walking_s = walking or None
    plan.metro_s = metro or None
    plan.transfer_s = transfer or None
    plan.transfer_count = transfer_count
    plan.legs = legs
    return plan


def plan_summary(segments: list[RouteSegment]) -> str:
    """用地铁/公交线路名生成方案摘要。"""

    names: list[str] = []
    for segment in segments:
        mode = (segment.mode or "").upper()
        if mode == "WALK":
            continue
        label = segment.line or ("公交" if mode == "BUS" else "")
        if label and label not in names:
            names.append(label)
    return " → ".join(names) or "公交地铁"


def _parse_one_transit(best: dict[str, Any]) -> tuple[int | None, list[RouteSegment]]:
    duration = _int_or_none(best.get("duration"))
    segments: list[RouteSegment] = []
    for raw in best.get("segments") or []:
        if not isinstance(raw, dict):
            continue
        segments.extend(_walking_segments(raw.get("walking")))
        segments.extend(_bus_segments(raw.get("bus")))
        segments.extend(_railway_segments(raw.get("railway")))
        segments.extend(_taxi_segments(raw.get("taxi")))
    return duration, segments


def chain_stations_as_line(line_name: str, stations: list[MetroStation]) -> MetroLine | None:
    """把同一线路的站点按最近邻连成参考折线，供公交线路接口失败时高亮。"""

    stops = [item for item in stations if line_name in item.lines]
    if len(stops) < 2:
        if len(stops) == 1:
            return MetroLine(
                name=line_name,
                path=[RoutePoint(lng=stops[0].lng, lat=stops[0].lat)],
            )
        return None
    remaining = list(stops)
    remaining.sort(key=lambda item: (item.lng, item.lat))
    current = remaining.pop(0)
    ordered = [current]
    while remaining:
        current = min(
            remaining,
            key=lambda item: haversine_distance_m(ordered[-1].lng, ordered[-1].lat, item.lng, item.lat),
        )
        remaining.remove(current)
        ordered.append(current)
    return MetroLine(name=line_name, path=_to_points([(item.lng, item.lat) for item in ordered]))


def unique_line_names(stations: list[MetroStation]) -> list[str]:
    """按出现顺序收集站点上的线路名。"""

    names: list[str] = []
    for station in stations:
        for line in station.lines:
            if line not in names:
                names.append(line)
    return names


def parse_bus_line_payload(payload: dict[str, Any] | None, line_name: str) -> MetroLine | None:
    """从高德公交线路查询结果中取出地铁线折线。"""

    if not payload:
        return None
    buslines = payload.get("buslines") or []
    chosen = None
    for item in buslines:
        if not isinstance(item, dict):
            continue
        text = f"{item.get('name') or ''} {item.get('type') or ''}"
        if "地铁" in text or line_name in text:
            chosen = item
            break
        if chosen is None:
            chosen = item
    if not chosen:
        return None
    path = _to_points(decode_polyline(_string(chosen.get("polyline"))))
    if len(path) < 2:
        return None
    return MetroLine(name=line_name, path=path)


def parse_riding_payload(payload: dict[str, Any] | None) -> tuple[int | None, list[RoutePoint]]:
    """解析高德骑行规划，得到时长和折线。"""

    if not payload:
        return None, []
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    paths = (data or {}).get("paths") or []
    if not paths or not isinstance(paths[0], dict):
        return None, []
    path = paths[0]
    points: list[RoutePoint] = []
    for step in path.get("steps") or []:
        if not isinstance(step, dict):
            continue
        points.extend(_to_points(decode_polyline(str(step.get("polyline") or ""))))
    if not points:
        points.extend(_to_points(decode_polyline(str(path.get("polyline") or ""))))
    return _int_or_none(path.get("duration")), points


def _walking_segments(walking: Any) -> list[RouteSegment]:
    block = walking if isinstance(walking, dict) else None
    if not block:
        return []
    points: list[RoutePoint] = []
    for step in block.get("steps") or []:
        if not isinstance(step, dict):
            continue
        points.extend(_to_points(decode_polyline(str(step.get("polyline") or ""))))
    if not points:
        return []
    duration = _int_or_none(block.get("duration"))
    if duration is None:
        duration = sum(_int_or_none(step.get("duration") if isinstance(step, dict) else None) or 0 for step in (block.get("steps") or [])) or None
    return [RouteSegment(mode="WALK", line="", duration_s=duration, path=points, stations=[])]


def _bus_segments(bus: Any) -> list[RouteSegment]:
    block = bus if isinstance(bus, dict) else None
    if not block:
        return []
    segments: list[RouteSegment] = []
    for line in block.get("buslines") or []:
        if not isinstance(line, dict):
            continue
        name = _string(line.get("name"))
        line_type = _string(line.get("type"))
        line_names = parse_line_names(name, line_type)
        mode = "SUBWAY" if "地铁" in name or "地铁" in line_type or line_names else "BUS"
        path = _to_points(decode_polyline(_string(line.get("polyline"))))
        if not path:
            continue
        stations = _stops_to_stations(line, line_names)
        segments.append(
            RouteSegment(
                mode=mode,
                line=line_names[0] if line_names else "",
                duration_s=_int_or_none(line.get("duration")),
                path=path,
                stations=stations,
            )
        )
    return segments


def _railway_segments(railway: Any) -> list[RouteSegment]:
    block = railway if isinstance(railway, dict) else None
    if not block:
        return []
    name = _string(block.get("name")) or _string(block.get("trip"))
    path = _to_points(decode_polyline(_string(block.get("polyline"))))
    if not path:
        departure = _location_pair((block.get("departure_stop") or {}) if isinstance(block.get("departure_stop"), dict) else {})
        arrival = _location_pair((block.get("arrival_stop") or {}) if isinstance(block.get("arrival_stop"), dict) else {})
        if departure and arrival:
            path = [RoutePoint(lng=departure[0], lat=departure[1]), RoutePoint(lng=arrival[0], lat=arrival[1])]
    if not path:
        return []
    return [RouteSegment(mode="RAILWAY", line=name, path=path, stations=[])]


def _taxi_segments(taxi: Any) -> list[RouteSegment]:
    block = taxi if isinstance(taxi, dict) else None
    if not block:
        return []
    origin = _split_location(block.get("origin"))
    destination = _split_location(block.get("destination"))
    if not origin or not destination:
        return []
    return [
        RouteSegment(
            mode="TAXI",
            line="",
            path=[RoutePoint(lng=origin[0], lat=origin[1]), RoutePoint(lng=destination[0], lat=destination[1])],
            stations=[],
        )
    ]


def _stops_to_stations(line: dict[str, Any], line_names: list[str]) -> list[MetroStation]:
    """提取上车站、途径站和下车站。"""

    stations: list[MetroStation] = []
    seen: set[str] = set()
    for stop in [line.get("departure_stop"), *(line.get("via_stops") or []), line.get("arrival_stop")]:
        if not isinstance(stop, dict):
            continue
        pair = _location_pair(stop)
        if pair is None:
            continue
        name = clean_station_name(_string(stop.get("name")))
        station_id = _string(stop.get("id")) or f"{pair[0]},{pair[1]}"
        if station_id in seen:
            continue
        seen.add(station_id)
        stations.append(
            MetroStation(
                id=station_id,
                name=name,
                lng=pair[0],
                lat=pair[1],
                lines=line_names,
            )
        )
    return stations


def _location_pair(stop: dict[str, Any]) -> tuple[float, float] | None:
    return _split_location(stop.get("location"))


def _split_location(value: Any) -> tuple[float, float] | None:
    text = _string(value)
    if "," not in text:
        return None
    lng_text, lat_text = text.split(",", maxsplit=1)
    try:
        return (float(lng_text), float(lat_text))
    except ValueError:
        return None


def _to_points(coords: list[tuple[float, float]]) -> list[RoutePoint]:
    return [RoutePoint(lng=lng, lat=lat) for lng, lat in coords]


def _string(value: Any) -> str:
    if value is None or isinstance(value, list):
        return ""
    return str(value)


def _int_or_none(value: Any) -> int | None:
    text = _string(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None
