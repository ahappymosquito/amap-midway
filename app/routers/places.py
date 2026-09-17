"""双点选址路由模块。

本文件提供按一个或多个通勤点搜索地点、单段地铁通勤时长，以及选店后地铁/骑行折线的接口。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.amap_client import AmapClient
from app.metro import parse_all_transit_plans, parse_riding_payload
from app.places import search_places_between
from app.routers.geocode import get_amap_client
from app.schemas import PlaceRouteResponse, PlacesSearchRequest, PlacesSearchResponse, TransitDurationResponse

router = APIRouter(prefix="/api", tags=["places"])


@router.post("/places/search", response_model=PlacesSearchResponse)
async def search_places(
    payload: PlacesSearchRequest,
    client: AmapClient = Depends(get_amap_client),
) -> PlacesSearchResponse:
    """按一个或多个通勤点搜索候选地点。"""

    return await search_places_between(
        client,
        origins=payload.origins,
        category=payload.category,
        budget_per_person=payload.budget_per_person,
        people_count=payload.people_count,
        city=payload.city.strip(),
        sort_by=payload.sort_by,
        radius_m=payload.radius_m,
        max_transit_min=payload.max_transit_min,
    )


@router.get("/places/transit", response_model=TransitDurationResponse)
async def transit_duration(
    origin_lng: Annotated[float, Query(ge=-180, le=180)],
    origin_lat: Annotated[float, Query(ge=-90, le=90)],
    dest_lng: Annotated[float, Query(ge=-180, le=180)],
    dest_lat: Annotated[float, Query(ge=-90, le=90)],
    city: Annotated[str, Query(max_length=40)] = "北京",
    client: AmapClient = Depends(get_amap_client),
) -> TransitDurationResponse:
    """查询两点之间公交/地铁方案时长。"""

    duration = await client.transit_duration(
        (origin_lng, origin_lat),
        (dest_lng, dest_lat),
        city.strip() or "北京",
    )
    return TransitDurationResponse(duration_s=duration)


@router.get("/places/route", response_model=PlaceRouteResponse)
async def place_route(
    origin_lng: Annotated[float, Query(ge=-180, le=180)],
    origin_lat: Annotated[float, Query(ge=-90, le=90)],
    dest_lng: Annotated[float, Query(ge=-180, le=180)],
    dest_lat: Annotated[float, Query(ge=-90, le=90)],
    city: Annotated[str, Query(max_length=40)] = "北京",
    client: AmapClient = Depends(get_amap_client),
) -> PlaceRouteResponse:
    """查询通勤点到候选店的地铁和骑行折线，供地图自行绘制。"""

    city_name = city.strip() or "北京"
    origin = (origin_lng, origin_lat)
    destination = (dest_lng, dest_lat)
    transit_payload = await client.transit_payload(origin, destination, city_name)
    riding_payload = await client.riding_payload(origin, destination)
    transit_plans = parse_all_transit_plans(transit_payload)
    riding_s, riding_path = parse_riding_payload(riding_payload)
    first = transit_plans[0] if transit_plans else None
    return PlaceRouteResponse(
        transit_s=first.duration_s if first else None,
        riding_s=riding_s,
        transit_segments=first.segments if first else [],
        transit_plans=transit_plans,
        riding_path=riding_path,
    )
