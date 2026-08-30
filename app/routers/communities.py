"""附近小区路由模块。

本文件提供按中心坐标和半径查询住宅小区 POI 的接口，并返回后端计算好的直线距离。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.amap_client import AmapClient
from app.routers.geocode import get_amap_client
from app.schemas import CommunitiesResponse

router = APIRouter(prefix="/api", tags=["communities"])


@router.get("/communities", response_model=CommunitiesResponse)
async def list_communities(
    lng: Annotated[float, Query(ge=-180, le=180)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    radius: Annotated[int, Query(ge=1, le=10000)] = 3000,
    client: AmapClient = Depends(get_amap_client),
) -> CommunitiesResponse:
    """查询指定中心点附近的住宅小区。"""

    communities = await client.search_communities(lng=lng, lat=lat, radius=radius)
    return CommunitiesResponse(center_lng=lng, center_lat=lat, radius_m=radius, communities=communities)
