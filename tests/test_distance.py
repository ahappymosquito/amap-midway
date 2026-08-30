"""距离计算测试。

本文件验证经纬度球面直线距离计算，确保附近小区接口返回的距离字段可信。
"""

from app.distance import haversine_distance_m


def test_haversine_distance_same_point_is_zero() -> None:
    assert haversine_distance_m(121.475, 31.229, 121.475, 31.229) == 0


def test_haversine_distance_for_one_latitude_degree() -> None:
    distance = haversine_distance_m(0, 0, 0, 1)

    assert 111_000 <= distance <= 112_000
