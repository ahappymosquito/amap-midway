"""高德 Web 服务客户端模块。

本文件封装高德地理编码、周边 POI/地铁站搜索、公交与骑行规划，并把高德响应转换为应用内部可用的结构。
"""

from typing import Any

import httpx
from fastapi import HTTPException, status

from app.distance import haversine_distance_m
from app.schemas import Community, LocationResponse, PlaceCategory, PoiRecord
from app.settings import Settings

PLACE_TYPES: dict[PlaceCategory, str] = {
    "restaurant": "050000",
    "hotel": "100000",
}

SKIP_NAME_MARKERS = ("医院", "食堂", "社区餐厅", "宴会厅", "停车场")


class AmapClient:
    """高德 Web 服务 API 客户端。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _require_key(self) -> str:
        if not self.settings.amap_web_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="缺少 AMAP_WEB_KEY 环境变量，无法调用高德服务。",
            )
        return self.settings.amap_web_key

    async def _get(
        self,
        path: str,
        params: dict[str, Any],
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        key = self._require_key()
        url = f"{self.settings.amap_web_api_base_url}{path}"
        query = {**params, "key": key}
        if client is None:
            async with httpx.AsyncClient(timeout=self.settings.amap_request_timeout) as owned:
                return await self._request(owned, url, query)
        return await self._request(client, url, query)

    async def _request(self, client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"高德服务请求失败：{exc}",
            ) from exc

        payload = response.json()
        if payload.get("status") != "1":
            message = payload.get("info") or "高德服务返回错误"
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message)
        return payload

    async def geocode(self, address: str, city: str = "") -> LocationResponse:
        """将结构化地址或地点名解析为经纬度，优先在指定城市内搜索。"""

        located = await self._locate_by_place(address, city)
        if located is not None:
            return located
        params: dict[str, Any] = {"address": address}
        if city:
            params["city"] = city
        payload = await self._get("/geocode/geo", params)
        geocodes = payload.get("geocodes") or []
        if not geocodes:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该地址对应的坐标。")

        first = geocodes[0]
        lng_text, lat_text = str(first["location"]).split(",", maxsplit=1)
        return LocationResponse(
            lng=float(lng_text),
            lat=float(lat_text),
            formatted_address=_string_or_empty(first.get("formatted_address")) or address,
            city=_city_from_geocode(first) or city,
        )

    async def _locate_by_place(self, address: str, city: str) -> LocationResponse | None:
        """用关键词搜把大厦、商场等地名解析为 POI 坐标。"""

        params: dict[str, Any] = {"keywords": address, "offset": 1, "page": 1, "extensions": "base"}
        if city:
            params["city"] = city
            params["citylimit"] = "true"
        payload = await self._get("/place/text", params)
        pois = payload.get("pois") or []
        if not pois:
            return None
        record = _parse_poi(pois[0])
        if record is None:
            return None
        poi_city = _string_or_empty(pois[0].get("cityname")) or _string_or_empty(pois[0].get("pname"))
        return LocationResponse(
            lng=record.lng,
            lat=record.lat,
            formatted_address=record.name if not record.address else f"{record.name}（{record.address}）",
            city=city or poi_city,
        )

    async def reverse_city(self, lng: float, lat: float) -> str:
        """用逆地理编码推断坐标所在城市。"""

        try:
            payload = await self._get(
                "/geocode/regeo",
                {"location": f"{lng},{lat}"},
            )
        except HTTPException:
            return ""
        component = ((payload.get("regeocode") or {}).get("addressComponent") or {})
        city = _string_or_empty(component.get("city"))
        if city:
            return city
        return _string_or_empty(component.get("province"))

    async def search_communities(self, lng: float, lat: float, radius: int) -> list[Community]:
        """搜索中心点附近住宅小区 POI。"""

        payload = await self._get(
            "/place/around",
            {
                "location": f"{lng},{lat}",
                "keywords": "住宅小区|小区",
                "radius": radius,
                "offset": 25,
                "page": 1,
                "extensions": "base",
            },
        )
        communities: list[Community] = []
        for poi in payload.get("pois") or []:
            record = _parse_poi(poi)
            if record is None:
                continue
            communities.append(
                Community(
                    id=record.id,
                    name=record.name,
                    lng=record.lng,
                    lat=record.lat,
                    address=record.address,
                    distance_m=haversine_distance_m(lng, lat, record.lng, record.lat),
                )
            )
        communities.sort(key=lambda item: item.distance_m)
        return communities

    async def search_around_pois(
        self,
        lng: float,
        lat: float,
        radius: int,
        category: PlaceCategory,
    ) -> list[PoiRecord]:
        """按品类搜索中心点附近的餐馆或酒店 POI。"""

        records: list[PoiRecord] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=self.settings.amap_request_timeout) as client:
            for page in (1, 2):
                payload = await self._get(
                    "/place/around",
                    {
                        "location": f"{lng},{lat}",
                        "types": PLACE_TYPES[category],
                        "radius": radius,
                        "offset": 25,
                        "page": page,
                        "extensions": "all",
                    },
                    client=client,
                )
                pois = payload.get("pois") or []
                if not pois:
                    break
                for poi in pois:
                    record = _parse_poi(poi)
                    if record is None or record.id in seen:
                        continue
                    if category == "restaurant" and _should_skip_restaurant(record.name):
                        continue
                    seen.add(record.id)
                    records.append(record)
        return records

    async def search_text_pois(
        self,
        keywords: str,
        city: str,
        types: str = "050000",
    ) -> list[PoiRecord]:
        """按关键词在指定城市搜 POI，供扫街榜必吃/烟火小店可视化。"""

        try:
            payload = await self._get(
                "/place/text",
                {
                    "keywords": keywords,
                    "city": city.strip() or "北京",
                    "citylimit": "true",
                    "types": types,
                    "offset": 25,
                    "page": 1,
                    "extensions": "all",
                },
            )
        except HTTPException:
            return []
        records: list[PoiRecord] = []
        seen: set[str] = set()
        for poi in payload.get("pois") or []:
            record = _parse_poi(poi)
            if record is None or record.id in seen:
                continue
            seen.add(record.id)
            records.append(record)
        return records

    async def measure_durations(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
        measure_type: int,
    ) -> list[int | None]:
        """批量测量多个起点到一个终点的驾车或步行时长，单位秒。"""

        if not origins:
            return []
        dest_lng, dest_lat = destination
        payload = await self._get(
            "/distance",
            {
                "origins": "|".join(f"{lng},{lat}" for lng, lat in origins),
                "destination": f"{dest_lng},{dest_lat}",
                "type": str(measure_type),
            },
        )
        results = payload.get("results") or []
        durations: list[int | None] = [None] * len(origins)
        for item in results:
            raw_index = _int_or_none(item.get("origin_id"))
            duration = _int_or_none(item.get("duration"))
            if raw_index is None:
                continue
            for candidate in (raw_index - 1, raw_index):
                if 0 <= candidate < len(origins) and durations[candidate] is None:
                    durations[candidate] = duration
                    break
        return durations

    async def search_metro_stations(self, lng: float, lat: float, radius: int) -> list[PoiRecord]:
        """搜索中心点附近的地铁站 POI，不含出入口。"""

        records: list[PoiRecord] = []
        seen: set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=self.settings.amap_request_timeout) as client:
                for page in (1, 2):
                    payload = await self._get(
                        "/place/around",
                        {
                            "location": f"{lng},{lat}",
                            "types": "150500",
                            "radius": radius,
                            "offset": 25,
                            "page": page,
                            "extensions": "base",
                        },
                        client=client,
                    )
                    pois = payload.get("pois") or []
                    if not pois:
                        break
                    for poi in pois:
                        record = _parse_poi(poi)
                        if record is None or record.id in seen:
                            continue
                        if record.typecode.startswith("150501"):
                            continue
                        seen.add(record.id)
                        records.append(record)
        except HTTPException:
            return []
        return records

    async def transit_payload(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        city: str,
    ) -> dict[str, Any] | None:
        """查询两点之间公交/地铁规划原始结果，失败时返回空。"""

        city_name = city.strip() or "北京"
        try:
            return await self._get(
                "/direction/transit/integrated",
                {
                    "origin": f"{origin[0]},{origin[1]}",
                    "destination": f"{destination[0]},{destination[1]}",
                    "city": city_name,
                    "cityd": city_name,
                    "strategy": "0",
                },
            )
        except HTTPException:
            return None

    async def transit_duration(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        city: str,
    ) -> int | None:
        """查询两点之间公交/地铁方案的时长，单位秒。无方案时返回空。"""

        payload = await self.transit_payload(origin, destination, city)
        transits = ((payload or {}).get("route") or {}).get("transits") or []
        if not transits:
            return None
        return _int_or_none(transits[0].get("duration"))

    async def riding_payload(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict[str, Any] | None:
        """查询两点之间骑行规划原始结果，失败时返回空。"""

        key = self._require_key()
        url = "https://restapi.amap.com/v4/direction/bicycling"
        async with httpx.AsyncClient(timeout=self.settings.amap_request_timeout) as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "key": key,
                        "origin": f"{origin[0]},{origin[1]}",
                        "destination": f"{destination[0]},{destination[1]}",
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError:
                return None
        payload = response.json()
        if payload.get("errcode") not in (0, "0", None):
            return None
        return payload

    async def riding_duration(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> int | None:
        """查询两点之间骑行时长，单位秒。"""

        payload = await self.riding_payload(origin, destination)
        paths = (((payload or {}).get("data") or {}).get("paths")) or []
        if not paths:
            return None
        return _int_or_none(paths[0].get("duration"))

    async def bus_line_payload(self, keyword: str, city: str) -> dict[str, Any] | None:
        """查询公交/地铁线路原始结果，失败时返回空。"""

        city_name = city.strip() or "北京"
        names = [keyword]
        if keyword and not keyword.startswith("地铁"):
            names.insert(0, f"地铁{keyword}")
        for name in names:
            try:
                payload = await self._get(
                    "/bus/line",
                    {"keywords": name, "city": city_name, "extensions": "all"},
                )
            except HTTPException:
                continue
            if payload.get("buslines"):
                return payload
        return None



def _parse_poi(poi: dict[str, Any]) -> PoiRecord | None:
    """把高德 POI 记录解析为内部结构，缺少坐标则丢弃。"""

    location = poi.get("location")
    if not location:
        return None
    lng_text, lat_text = str(location).split(",", maxsplit=1)
    lng = float(lng_text)
    lat = float(lat_text)
    biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
    return PoiRecord(
        id=str(poi.get("id") or f"{lng},{lat}"),
        name=str(poi.get("name") or "未命名地点"),
        lng=lng,
        lat=lat,
        address=_string_or_empty(poi.get("address")),
        rating=_string_or_none(biz_ext.get("rating") if biz_ext else None),
        cost=_float_or_none(biz_ext.get("cost") if biz_ext else None),
        typecode=_string_or_empty(poi.get("typecode")),
        tag=_string_or_empty(poi.get("tag")),
    )


def _should_skip_restaurant(name: str) -> bool:
    """过滤医院食堂、宴会厅等不适合碰面的餐饮 POI。"""

    return any(marker in name for marker in SKIP_NAME_MARKERS)


def _city_from_geocode(first: dict[str, Any]) -> str:
    """从地理编码结果中取出城市名。"""

    city = _string_or_empty(first.get("city"))
    if city:
        return city
    return _string_or_empty(first.get("province"))


def _string_or_empty(value: Any) -> str:
    """把高德可能返回的列表或空值统一转换为字符串。"""

    if value is None or isinstance(value, list):
        return ""
    return str(value)


def _string_or_none(value: Any) -> str | None:
    text = _string_or_empty(value)
    return text or None


def _float_or_none(value: Any) -> float | None:
    text = _string_or_empty(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int_or_none(value: Any) -> int | None:
    text = _string_or_empty(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None
