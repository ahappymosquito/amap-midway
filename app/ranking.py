"""扫街榜分类配置。

本文件对齐高德扫街榜2026状元榜六类（美食、酒店、景点、咖啡、酒吧、玩乐），提供 POI 类型、榜单地址和附近搭配推荐规则。网页暂无咖啡/酒吧/玩乐独立榜时回扫街榜总览。
"""

from app.schemas import PlaceCategory

PLACE_TYPES: dict[PlaceCategory, str] = {
    "restaurant": "050000",
    "hotel": "100000",
    "coffee": "050500",
    "bar": "080302",
    "play": "080300|141200",
    "scenic": "110000",
}

CATEGORY_LABELS: dict[PlaceCategory, str] = {
    "restaurant": "美食",
    "hotel": "酒店",
    "play": "玩乐",
    "coffee": "咖啡",
    "bar": "酒吧",
    "scenic": "景点",
}

# 网页已确认的路径：food/hotel/scenic/shop；咖啡/酒吧/玩乐回总览。
RANKING_KIND: dict[PlaceCategory, str] = {
    "restaurant": "food",
    "hotel": "hotel",
    "scenic": "scenic",
    "coffee": "food",
    "bar": "food",
    "play": "food",
}

CHAMPION_KEYWORDS: dict[PlaceCategory, str] = {
    "restaurant": "状元榜",
    "coffee": "必喝咖啡",
    "bar": "必去酒吧",
    "play": "玩乐",
    "scenic": "必去景点",
}

STREET_KEYWORD = "烟火小店"
SELECT_KEYWORD = "品质甄选"

COMPANION_COUNT = 3


def companion_category(category: PlaceCategory) -> PlaceCategory | None:
    """吃饭类搭配附近玩乐，玩乐/景点搭配附近美食，做成轻量行程推荐。"""

    if category in ("restaurant", "coffee", "bar"):
        return "play"
    if category in ("play", "scenic"):
        return "restaurant"
    return None


def ranking_kind_for(category: str) -> str:
    return RANKING_KIND.get(category, "food")  # type: ignore[arg-type]
