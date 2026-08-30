"""高德客户端测试。

本文件使用 mock 传输层验证高德地理编码、周边搜索、空结果和错误响应的转换逻辑。
"""

import httpx
import pytest
import respx
from fastapi import HTTPException

from app.amap_client import AmapClient
from app.settings import Settings


@pytest.mark.asyncio
@respx.mock
async def test_geocode_success() -> None:
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(200, json={"status": "1", "pois": []})
    )
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "geocodes": [{"location": "121.475000,31.229000", "formatted_address": "上海市人民广场"}],
            },
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    result = await client.geocode("人民广场")

    assert result.lng == 121.475
    assert result.lat == 31.229
    assert result.formatted_address == "上海市人民广场"


@pytest.mark.asyncio
@respx.mock
async def test_geocode_empty_result_raises_404() -> None:
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(200, json={"status": "1", "pois": []})
    )
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "geocodes": []})
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    with pytest.raises(HTTPException) as exc_info:
        await client.geocode("不存在的位置")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_geocode_prefers_city_limited_poi() -> None:
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [{"id": "B000A84SEH", "name": "中国黄金大厦", "location": "116.406180,39.959491", "address": "柳荫公园南街1号"}],
            },
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    result = await client.geocode("中国黄金大厦", city="北京")

    assert result.lng == 116.40618
    assert result.city == "北京"


@pytest.mark.asyncio
@respx.mock
async def test_geocode_infers_city_from_poi() -> None:
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {
                        "id": "B000A84SEH",
                        "name": "北控水务大厦",
                        "location": "116.492661,39.996856",
                        "address": "崔各庄",
                        "cityname": "北京市",
                    }
                ],
            },
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    result = await client.geocode("北控水务大厦")

    assert result.city == "北京市"


@pytest.mark.asyncio
@respx.mock
async def test_search_communities_success_sorts_by_distance() -> None:
    respx.get("https://restapi.amap.com/v3/place/around").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {"id": "far", "name": "远小区", "location": "121.490000,31.240000", "address": "远路"},
                    {"id": "near", "name": "近小区", "location": "121.476000,31.230000", "address": "近路"},
                ],
            },
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    results = await client.search_communities(121.475, 31.229, 3000)

    assert [item.id for item in results] == ["near", "far"]
    assert results[0].distance_m >= 0


@pytest.mark.asyncio
@respx.mock
async def test_search_around_pois_skips_hospital_canteen() -> None:
    respx.get("https://restapi.amap.com/v3/place/around").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {
                        "id": "keep",
                        "name": "海底捞火锅",
                        "location": "116.447306,39.971412",
                        "address": "凯德B1",
                        "typecode": "050117",
                        "biz_ext": {"rating": "4.7", "cost": "120.00"},
                    },
                    {
                        "id": "skip",
                        "name": "中日友好医院本部餐厅",
                        "location": "116.43,39.97",
                        "address": "医院",
                        "typecode": "050100",
                        "biz_ext": {},
                    },
                ],
            },
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    results = await client.search_around_pois(116.448, 39.974, 2000, "restaurant")

    assert [item.id for item in results] == ["keep"]
    assert results[0].cost == 120.0


@pytest.mark.asyncio
@respx.mock
async def test_measure_durations_supports_one_based_origin_id() -> None:
    respx.get("https://restapi.amap.com/v3/distance").mock(
        return_value=httpx.Response(
            200,
            json={"status": "1", "results": [{"origin_id": "1", "duration": "880", "distance": "5400"}]},
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    results = await client.measure_durations([(116.49, 39.99)], (116.45, 39.97), 1)

    assert results == [880]


@pytest.mark.asyncio
@respx.mock
async def test_search_metro_stations_skips_exits() -> None:
    respx.get("https://restapi.amap.com/v3/place/around").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {
                        "id": "station",
                        "name": "知春路(地铁站)",
                        "location": "116.448,39.976",
                        "address": "10号线;13号线",
                        "typecode": "150500",
                    },
                    {
                        "id": "exit",
                        "name": "知春路A口",
                        "location": "116.448,39.976",
                        "address": "10号线",
                        "typecode": "150501",
                    },
                ],
            },
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    results = await client.search_metro_stations(116.448, 39.976, 3000)

    assert [item.id for item in results] == ["station"]


@pytest.mark.asyncio
@respx.mock
async def test_bus_line_payload_prefers_metro_keyword() -> None:
    respx.get("https://restapi.amap.com/v3/bus/line").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "buslines": [{"name": "地铁10号线", "type": "地铁线路", "polyline": "116.49,39.99;116.45,39.97"}],
            },
        )
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    payload = await client.bus_line_payload("10号线", "北京")

    assert payload is not None
    assert payload["buslines"][0]["name"] == "地铁10号线"


@pytest.mark.asyncio
@respx.mock
async def test_amap_error_raises_bad_gateway() -> None:
    respx.get("https://restapi.amap.com/v3/place/around").mock(
        return_value=httpx.Response(200, json={"status": "0", "info": "INVALID_USER_KEY"})
    )
    client = AmapClient(Settings(AMAP_WEB_KEY="test-key"))

    with pytest.raises(HTTPException) as exc_info:
        await client.search_communities(121.475, 31.229, 3000)

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "INVALID_USER_KEY"
