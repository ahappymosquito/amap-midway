"""选址接口测试。

本文件验证一到多个通勤点搜索参数校验、差标字段，以及候选结果对高德客户端的集成行为。
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routers.geocode import get_amap_client
from app.schemas import Community, LocationResponse, PoiRecord
from app.settings import Settings, get_settings


class FakeAmapClient:
    async def geocode(self, address: str, city: str = "") -> LocationResponse:
        if "北控" in address:
            return LocationResponse(lng=116.492661, lat=39.996856, formatted_address=address, city=city or "北京")
        return LocationResponse(lng=116.406180, lat=39.959491, formatted_address=address, city=city or "北京")

    async def reverse_geocode(self, lng: float, lat: float) -> LocationResponse:
        return LocationResponse(lng=lng, lat=lat, formatted_address="望京街附近", city="北京")

    async def reverse_city(self, lng: float, lat: float) -> str:
        located = await self.reverse_geocode(lng, lat)
        return located.city

    async def search_communities(self, lng: float, lat: float, radius: int) -> list[Community]:
        return []

    async def search_around_pois(self, lng: float, lat: float, radius: int, category: str) -> list[PoiRecord]:
        return [
            PoiRecord(id="cheap", name="萨莉亚", lng=lng, lat=lat, address="凯德B1", rating="4.5", cost=54),
            PoiRecord(id="pricey-hotel", name="皇冠假日", lng=lng + 0.002, lat=lat, address="太阳宫桥", rating="4.5", cost=835),
        ]

    async def search_text_pois(self, keywords: str, city: str, types: str = "050000") -> list[PoiRecord]:
        if "状元" in keywords or "必吃" in keywords:
            return [PoiRecord(id="cheap", name="萨莉亚", lng=116.45, lat=39.98, address="凯德B1", rating="4.8", cost=54)]
        if "烟火" in keywords:
            return [PoiRecord(id="street", name="胡同面馆", lng=116.45, lat=39.98, address="小巷", rating="4.2", cost=28)]
        if "温泉" in keywords:
            return [PoiRecord(id="spring-hotel", name="朗丽兹温泉酒店", lng=116.45, lat=39.98, address="小汤山", rating="4.6", cost=480)]
        if "电竞" in keywords:
            return [
                PoiRecord(id="esports-hotel", name="雷神电竞酒店", lng=116.45, lat=39.98, address="望京", rating="4.4", cost=198),
                PoiRecord(id="esports-decoy", name="顺业精品酒店", lng=116.45, lat=39.98, address="天通苑", rating="4.1", cost=220),
            ]
        if "汉庭" in keywords or "全季" in keywords:
            return [PoiRecord(id="hanting", name="汉庭酒店(望京店)", lng=116.45, lat=39.98, address="望京", rating="4.3", cost=320)]
        if "大床" in keywords:
            return [PoiRecord(id="king-hotel", name="雅致大床房酒店", lng=116.45, lat=39.98, address="太阳宫", rating="4.1", cost=260)]
        if "套房" in keywords:
            return [PoiRecord(id="suite-hotel", name="望京商务套房酒店", lng=116.45, lat=39.98, address="望京", rating="4.2", cost=520)]
        return []

    async def transit_duration(self, origin, destination, city: str) -> int | None:
        return 1500

    async def riding_duration(self, origin, destination) -> int | None:
        return 1200

    async def search_metro_stations(self, lng: float, lat: float, radius: int) -> list[PoiRecord]:
        return [
            PoiRecord(
                id="metro-in",
                name="知春路(地铁站)",
                lng=lng,
                lat=lat,
                address="10号线;13号线",
                typecode="150500",
            ),
            PoiRecord(
                id="metro-exit",
                name="知春路A口",
                lng=lng,
                lat=lat,
                address="10号线",
                typecode="150501",
            ),
        ]

    async def transit_payload(self, origin, destination, city: str) -> dict:
        return {
            "status": "1",
            "route": {
                "transits": [
                    {
                        "duration": "1500",
                        "segments": [
                            {
                                "bus": {
                                    "buslines": [
                                        {
                                            "name": "地铁10号线(巴沟--苏州街)",
                                            "type": "地铁线路",
                                            "polyline": "116.49,39.99;116.45,39.97",
                                            "departure_stop": {
                                                "name": "知春路",
                                                "id": "s1",
                                                "location": "116.49,39.99",
                                            },
                                            "arrival_stop": {
                                                "name": "芍药居",
                                                "id": "s2",
                                                "location": "116.45,39.97",
                                            },
                                        }
                                    ]
                                }
                            }
                        ],
                    }
                ]
            },
        }

    async def riding_payload(self, origin, destination) -> dict:
        return {
            "errcode": 0,
            "data": {"paths": [{"duration": "1200", "steps": [{"polyline": "116.49,39.99;116.45,39.97"}]}]},
        }

    async def bus_line_payload(self, keyword: str, city: str) -> dict:
        return {
            "status": "1",
            "buslines": [
                {
                    "name": f"地铁{keyword}" if not str(keyword).startswith("地铁") else keyword,
                    "type": "地铁线路",
                    "polyline": "116.49,39.99;116.45,39.97;116.43,39.96",
                }
            ],
        }

    async def measure_durations(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
        measure_type: int,
    ) -> list[int | None]:
        return [900 + index * 60 for index in range(len(origins))]


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(AMAP_WEB_KEY="test-key")
    app.dependency_overrides[get_amap_client] = lambda: FakeAmapClient()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_places_search_returns_ranked_candidates(client: TestClient) -> None:
    response = client.post(
        "/api/places/search",
        json={
            "origins": [{"address": "北控水务大厦"}, {"address": "中国黄金大厦"}],
            "category": "hotel",
            "people_count": 2,
            "budget_per_person": 300,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["budget_total"] == 600
    assert payload["people_count"] == 2
    assert payload["origins"][0]["city"] == "北京"
    names = [item["name"] for item in payload["places"]]
    assert "萨莉亚" in names
    assert names.index("萨莉亚") < names.index("皇冠假日")
    hotel = next(item for item in payload["places"] if item["name"] == "皇冠假日")
    assert hotel["over_budget"] is True
    assert hotel["commutes"][0]["transit_s"] == 1500
    assert hotel["open_links"]["ctrip"]
    assert "cityId=" in hotel["open_links"]["ctrip"]
    assert "searchWord=" in hotel["open_links"]["ctrip"]
    assert "hotel/list/list.html" in hotel["open_links"]["meituan"]
    assert "callnative=0" in hotel["open_links"]["amap"]
    assert payload["metro_stations"][0]["name"] == "知春路"
    assert payload["metro_stations"][0]["lines"] == ["10号线", "13号线"]
    assert all(item["id"] != "metro-exit" for item in payload["metro_stations"])
    assert payload["metro_lines"] == []
    assert payload["places"][0]["origin_routes"]
    assert payload["places"][0]["origin_routes"][0]["transit_plans"][0]["summary"] == "10号线"
    assert payload["places"][0]["origin_routes"][0]["riding_path"]


def test_transit_duration_endpoint(client: TestClient) -> None:
    response = client.get(
        "/api/places/transit",
        params={
            "origin_lng": 116.49,
            "origin_lat": 39.99,
            "dest_lng": 116.45,
            "dest_lat": 39.97,
            "city": "北京",
        },
    )

    assert response.status_code == 200
    assert response.json()["duration_s"] == 1500


def test_place_route_returns_polylines(client: TestClient) -> None:
    response = client.get(
        "/api/places/route",
        params={
            "origin_lng": 116.49,
            "origin_lat": 39.99,
            "dest_lng": 116.45,
            "dest_lat": 39.97,
            "city": "北京",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transit_s"] == 1500
    assert payload["riding_s"] == 1200
    assert payload["transit_segments"][0]["line"] == "10号线"
    assert payload["transit_segments"][0]["path"][0] == {"lng": 116.49, "lat": 39.99}
    assert payload["transit_plans"][0]["summary"] == "10号线"
    assert payload["riding_path"][-1] == {"lng": 116.45, "lat": 39.97}


def test_hotel_search_marks_attribute_and_bed_filters(client: TestClient) -> None:
    response = client.post(
        "/api/places/search",
        json={
            "origins": [{"address": "北控水务大厦"}, {"address": "中国黄金大厦"}],
            "category": "hotel",
            "people_count": 2,
            "budget_per_person": 300,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["places"]}
    assert by_name["朗丽兹温泉酒店"]["hotel_attrs"] == ["hotspring"]
    assert by_name["雷神电竞酒店"]["hotel_attrs"] == ["esports"]
    assert by_name["汉庭酒店(望京店)"]["hotel_attrs"] == ["huazhu"]
    assert by_name["雅致大床房酒店"]["bed_types"] == ["king"]
    assert by_name["望京商务套房酒店"]["bed_types"] == ["suite"]
    assert "顺业精品酒店" not in by_name
    assert "amap.com/ranking/" in payload["amap_ranking_url"]


def test_restaurant_search_marks_saojie_boards(client: TestClient) -> None:
    response = client.post(
        "/api/places/search",
        json={
            "origins": [{"address": "北控水务大厦"}, {"address": "中国黄金大厦"}],
            "category": "restaurant",
            "people_count": 2,
            "budget_per_person": 300,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["places"]}
    assert by_name["萨莉亚"]["board"] == "champion"
    assert by_name["胡同面馆"]["board"] == "street"
    assert "amap.com/ranking/" in payload["amap_ranking_url"]


def test_places_search_accepts_single_origin(client: TestClient) -> None:
    response = client.post(
        "/api/places/search",
        json={"origins": [{"address": "中国黄金大厦"}], "category": "restaurant"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["origins"]) == 1
    assert payload["radius_m"] == 1500
    assert payload["places"]


def test_places_search_accepts_coordinate_origin(client: TestClient) -> None:
    response = client.post(
        "/api/places/search",
        json={"origins": [{"lng": 116.48, "lat": 39.99}], "category": "restaurant"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["origins"][0]["formatted_address"] == "望京街附近"
    assert payload["origins"][0]["city"] == "北京"


def test_places_search_requires_origin(client: TestClient) -> None:
    response = client.post(
        "/api/places/search",
        json={"origins": [], "category": "restaurant"},
    )

    assert response.status_code == 422
