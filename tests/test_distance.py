"""距离计算测试。

本文件验证经纬度球面直线距离和单点/多点搜索半径，确保附近搜索范围可信。
"""

from app.distance import haversine_distance_m, search_radius_from_points


def test_haversine_distance_same_point_is_zero() -> None:
    assert haversine_distance_m(121.475, 31.229, 121.475, 31.229) == 0


def test_haversine_distance_for_one_latitude_degree() -> None:
    distance = haversine_distance_m(0, 0, 0, 1)

    assert 111_000 <= distance <= 112_000


def test_search_radius_single_point_uses_minimum() -> None:
    assert search_radius_from_points([(116.48, 39.99)]) == 1500
