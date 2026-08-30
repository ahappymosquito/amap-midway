"""接口数据模型模块。

本文件定义配置、地理编码、多点选址、地铁站与线路、多种出行方案折线和网页看价外链的 Pydantic 模型。
"""

from typing import Literal

from pydantic import BaseModel, Field

PlaceCategory = Literal["restaurant", "hotel"]


class ConfigResponse(BaseModel):
    """前端运行所需配置。"""

    amap_key_configured: bool
    amap_js_key: str | None = None


class LocationResponse(BaseModel):
    """地址解析后的坐标。"""

    lng: float
    lat: float
    formatted_address: str
    city: str = ""


class Community(BaseModel):
    """住宅小区 POI 信息。"""

    id: str
    name: str
    lng: float
    lat: float
    address: str = ""
    distance_m: int = Field(ge=0)


class CommunitiesResponse(BaseModel):
    """附近小区搜索结果。"""

    center_lng: float
    center_lat: float
    radius_m: int
    communities: list[Community]


class OriginInput(BaseModel):
    """选址起点，允许地址或坐标。"""

    address: str | None = Field(default=None, max_length=120)
    lng: float | None = Field(default=None, ge=-180, le=180)
    lat: float | None = Field(default=None, ge=-90, le=90)


class PlacesSearchRequest(BaseModel):
    """多个通勤点之间搜索餐馆或酒店。"""

    origins: list[OriginInput] = Field(min_length=2, max_length=6)
    category: PlaceCategory
    city: str = Field(default="", max_length=40)
    people_count: int = Field(default=2, ge=1, le=8)
    budget_per_person: int = Field(default=300, ge=50, le=5000)


class CommuteTimes(BaseModel):
    """从某一通勤点到候选地点的地铁和骑行时长，单位秒。"""

    transit_s: int | None = None
    riding_s: int | None = None
    walking_s: int | None = None
    driving_s: int | None = None


class OpenLinks(BaseModel):
    """跳转高德、美团、携程、点评查看详情和价格的链接。"""

    amap: str
    amap_app: str
    meituan: str
    meituan_app: str
    ctrip: str | None = None
    dianping: str | None = None


class MetroStation(BaseModel):
    """通勤点之间的地铁站参考标注。"""

    id: str
    name: str
    lng: float
    lat: float
    lines: list[str] = Field(default_factory=list)


class RoutePoint(BaseModel):
    """路线折线的一个坐标点。"""

    lng: float
    lat: float


class RouteSegment(BaseModel):
    """公交/地铁方案中的一段折线。"""

    mode: str
    line: str = ""
    duration_s: int | None = None
    path: list[RoutePoint] = Field(default_factory=list)
    stations: list[MetroStation] = Field(default_factory=list)


class RouteLeg(BaseModel):
    """出行方案中的一段说明，供悬停明细表使用。"""

    label: str
    mode: str
    duration_s: int | None = None


class TransitPlan(BaseModel):
    """一条公交/地铁出行方案。"""

    duration_s: int | None = None
    summary: str = ""
    walking_s: int | None = None
    metro_s: int | None = None
    transfer_s: int | None = None
    transfer_count: int = 0
    legs: list[RouteLeg] = Field(default_factory=list)
    segments: list[RouteSegment] = Field(default_factory=list)


class OriginRoutes(BaseModel):
    """从一个通勤点到候选店的多种地铁方案和一条骑行方案。"""

    transit_plans: list[TransitPlan] = Field(default_factory=list)
    riding_s: int | None = None
    riding_path: list[RoutePoint] = Field(default_factory=list)


class Place(BaseModel):
    """多点选址候选餐馆或酒店。"""

    id: str
    name: str
    lng: float
    lat: float
    address: str = ""
    category: PlaceCategory
    rating: str | None = None
    cost: float | None = None
    commutes: list[CommuteTimes]
    fairness_s: int = Field(ge=0)
    over_budget: bool = False
    budget_unknown: bool = False
    open_links: OpenLinks
    origin_routes: list[OriginRoutes] = Field(default_factory=list)
    board: str | None = None


class MetroLine(BaseModel):
    """一条地铁线路的参考折线，用于地图高亮。"""

    name: str
    path: list[RoutePoint] = Field(default_factory=list)


class PlacesSearchResponse(BaseModel):
    """多点选址结果。"""

    origins: list[LocationResponse]
    midpoint_lng: float
    midpoint_lat: float
    radius_m: int
    category: PlaceCategory
    people_count: int
    budget_per_person: int
    budget_total: int
    places: list[Place]
    metro_stations: list[MetroStation] = Field(default_factory=list)
    metro_lines: list[MetroLine] = Field(default_factory=list)


class TransitDurationResponse(BaseModel):
    """单段公交/地铁通勤时长。"""

    duration_s: int | None = None


class PlaceRouteResponse(BaseModel):
    """选店后各地到店的多种地铁方案和骑行折线，供前端自行绘制。"""

    transit_s: int | None = None
    riding_s: int | None = None
    transit_segments: list[RouteSegment] = Field(default_factory=list)
    transit_plans: list[TransitPlan] = Field(default_factory=list)
    riding_path: list[RoutePoint] = Field(default_factory=list)


class PoiRecord(BaseModel):
    """高德周边搜索解析后的原始 POI。"""

    id: str
    name: str
    lng: float
    lat: float
    address: str = ""
    rating: str | None = None
    cost: float | None = None
    typecode: str = ""
    tag: str = ""
