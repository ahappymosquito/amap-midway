"""地理编码路由模块。

本文件提供地址转坐标，以及输入地名时的候选地点提示。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.amap_client import AmapClient
from app.schemas import LocationResponse, PlaceTipsResponse
from app.settings import Settings, get_settings

router = APIRouter(prefix="/api", tags=["geocode"])


def get_amap_client(settings: Settings = Depends(get_settings)) -> AmapClient:
    """创建高德客户端依赖。"""

    return AmapClient(settings)


@router.get("/geocode", response_model=LocationResponse)
async def geocode_address(
    address: Annotated[str, Query(min_length=1, max_length=120)],
    city: Annotated[str, Query(max_length=40)] = "北京",
    client: AmapClient = Depends(get_amap_client),
) -> LocationResponse:
    """将地址解析为经纬度。"""

    return await client.geocode(address.strip(), city=city.strip())


@router.get("/geocode/suggest", response_model=PlaceTipsResponse)
async def suggest_places(
    q: Annotated[str, Query(min_length=1, max_length=80)],
    city: Annotated[str, Query(max_length=40)] = "",
    client: AmapClient = Depends(get_amap_client),
) -> PlaceTipsResponse:
    """按正在输入的地名返回候选地点。"""

    return PlaceTipsResponse(tips=await client.input_tips(q.strip(), city=city.strip()))
