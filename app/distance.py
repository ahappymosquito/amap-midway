"""距离计算模块。

本文件实现经纬度球面距离、多点中心和搜索半径，供小区搜索和多点选址复用。
"""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_008.8
MIN_SEARCH_RADIUS_M = 1500
MAX_SEARCH_RADIUS_M = 8000


def haversine_distance_m(lng1: float, lat1: float, lng2: float, lat2: float) -> int:
    """计算两点之间的球面直线距离，返回四舍五入后的米数。"""

    lng1_rad, lat1_rad, lng2_rad, lat2_rad = map(radians, (lng1, lat1, lng2, lat2))
    delta_lng = lng2_rad - lng1_rad
    delta_lat = lat2_rad - lat1_rad
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
    return round(2 * EARTH_RADIUS_M * asin(sqrt(a)))


def midpoint(lng1: float, lat1: float, lng2: float, lat2: float) -> tuple[float, float]:
    """返回两点经纬度的算术中点。"""

    return ((lng1 + lng2) / 2, (lat1 + lat2) / 2)


def search_radius_m(lng1: float, lat1: float, lng2: float, lat2: float) -> int:
    """按两点间距的一半加余量得到周边搜索半径，并限制在 1.5km 到 8km。"""

    return search_radius_from_points([(lng1, lat1), (lng2, lat2)])


def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """返回多个点的算术中心。"""

    if not points:
        raise ValueError("至少需要一个坐标")
    lng = sum(item[0] for item in points) / len(points)
    lat = sum(item[1] for item in points) / len(points)
    return (lng, lat)


def search_radius_from_points(points: list[tuple[float, float]]) -> int:
    """按各点到中心的最远距离加余量得到搜索半径，限制在 1.5km 到 8km。"""

    center_lng, center_lat = centroid(points)
    farthest = max(haversine_distance_m(center_lng, center_lat, lng, lat) for lng, lat in points)
    return int(min(MAX_SEARCH_RADIUS_M, max(MIN_SEARCH_RADIUS_M, farthest * 1.2)))
