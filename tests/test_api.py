"""API 路由测试。

本文件验证配置接口、参数校验以及附近小区接口对高德客户端依赖的集成行为。
"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routers.geocode import get_amap_client
from app.schemas import Community
from app.settings import Settings, get_settings


class FakeAmapClient:
    async def geocode(self, address: str, city: str = ""):
        return {"lng": 121.475, "lat": 31.229, "formatted_address": address, "city": city or "上海市"}

    async def search_communities(self, lng: float, lat: float, radius: int) -> list[Community]:
        return [
            Community(
                id="poi-1",
                name="测试小区",
                lng=lng + 0.001,
                lat=lat + 0.001,
                address="测试路 1 号",
                distance_m=156,
            )
        ]


@pytest.fixture
def client() -> AsyncIterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(AMAP_WEB_KEY="test-key")
    app.dependency_overrides[get_amap_client] = lambda: FakeAmapClient()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_config_returns_key_status(client: TestClient) -> None:
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {"amap_key_configured": True, "amap_js_key": "test-key"}


def test_communities_accepts_valid_radius(client: TestClient) -> None:
    response = client.get("/api/communities", params={"lng": 121.475, "lat": 31.229, "radius": 3000})

    assert response.status_code == 200
    payload = response.json()
    assert payload["radius_m"] == 3000
    assert payload["communities"][0]["name"] == "测试小区"


def test_communities_rejects_too_large_radius(client: TestClient) -> None:
    response = client.get("/api/communities", params={"lng": 121.475, "lat": 31.229, "radius": 10001})

    assert response.status_code == 422
