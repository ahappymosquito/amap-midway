"""携程酒店房型查询测试。

本文件用 mock 传输层验证店名匹配、点评侧房型列表归类，以及失败时不打断选址结果。
"""

import httpx
import pytest
import respx

from app import ctrip_rooms
from app.ctrip_rooms import COMMENT_URL, SEARCH_URL, _best_match, lookup_hotel_rooms


@pytest.fixture(autouse=True)
def clear_ctrip_cache() -> None:
    ctrip_rooms._cache.clear()


@pytest.mark.asyncio
@respx.mock
async def test_lookup_maps_ctrip_room_filters_to_bed_types() -> None:
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "Result": True,
                "Response": {
                    "searchResults": [
                        {"id": "45565522", "type": "Hotel", "word": "全季酒店(北京望京店)", "cityId": 1},
                    ]
                },
            },
        )
    )
    respx.post(COMMENT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "roomFilterList": [
                    "高级大床房（65寸投屏电视＋好眠床垫）",
                    "高级双床房（65寸投屏电视＋好眠床垫）",
                    "家庭房",
                    "豪华套房",
                ]
            },
        )
    )

    async with httpx.AsyncClient() as client:
        rooms, beds = await lookup_hotel_rooms(client, "全季酒店(北京望京店)", 1)

    assert "高级大床房（65寸投屏电视＋好眠床垫）" in rooms
    assert beds == ["king", "twin", "family", "suite"]


@pytest.mark.asyncio
@respx.mock
async def test_lookup_returns_empty_when_ctrip_blocked() -> None:
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(403, json={"message": "Operation Forbidden."}))

    async with httpx.AsyncClient() as client:
        rooms, beds = await lookup_hotel_rooms(client, "不存在的酒店", 1)

    assert rooms == []
    assert beds == []


def test_best_match_rejects_loose_mall_name() -> None:
    results = [
        {"id": "1", "type": "Hotel", "word": "海友酒店(北京望京SOHO新荟城店)", "cityId": 1},
        {"id": "2", "type": "Hotel", "word": "全季酒店(北京望京店)", "cityId": 1},
    ]
    assert _best_match(results, "新荟城店(北京)", 1) is None
    matched = _best_match(results, "全季酒店(北京望京SOHO店)", 1)
    assert matched is not None
    assert matched["id"] == "2"
