"""外链与差标测试。

本文件验证高德/美团/携程/点评跳转链接生成（含城市参数），以及一人 300、两人 600 的差标判断。
"""

import re

from app.budget import couple_budget, is_over_budget
from app.distance import centroid, midpoint, search_radius_from_points, search_radius_m
from app.open_links import build_open_links, plain_city


def test_restaurant_links_include_meituan_and_dianping() -> None:
    links = build_open_links(
        name="海底捞",
        lng=116.45,
        lat=39.97,
        category="restaurant",
        poi_id="B000A96NAA",
        city="北京市",
    )

    assert "uri.amap.com/marker" in links.amap
    assert "callnative=0" in links.amap
    assert "B000A96NAA" in links.amap_app
    assert "meishi.meituan.com" in links.meituan
    assert "ci=1" in links.meituan
    assert links.dianping is not None
    assert "/keyword/2/10_" in links.dianping
    assert links.ctrip is None


def test_hotel_links_include_ctrip_city_and_search_word() -> None:
    links = build_open_links(
        name="德全奢品酒店",
        lng=116.43,
        lat=39.98,
        category="hotel",
        poi_id="B0M6OSLL15",
        city="北京市",
    )

    assert links.ctrip is not None
    assert "hotels.ctrip.com/hotels/list" in links.ctrip
    assert "cityId=1" in links.ctrip
    assert "searchWord=" in links.ctrip
    assert "cityName=" in links.ctrip
    assert re.search(r"checkin=\d{4}-\d{2}-\d{2}", links.ctrip)
    assert "hotel/list/list.html" in links.meituan
    assert "cityId=1" in links.meituan
    assert links.dianping is None


def test_plain_city_strips_suffix() -> None:
    assert plain_city("北京市") == "北京"
    assert plain_city("上海市") == "上海"


def test_couple_budget_stacks_per_person() -> None:
    assert couple_budget(300) == 600


def test_restaurant_over_budget_uses_per_person() -> None:
    assert is_over_budget("restaurant", 301, 300) is True
    assert is_over_budget("restaurant", 120, 300) is False


def test_hotel_over_budget_uses_people_count() -> None:
    assert couple_budget(300, 3) == 900
    assert is_over_budget("hotel", 763, 300, 2) is True
    assert is_over_budget("hotel", 471, 300, 2) is False
    assert is_over_budget("hotel", 800, 300, 3) is False
    assert is_over_budget("hotel", None, 300, 2) is False


def test_search_radius_is_clamped() -> None:
    close = search_radius_m(116.45, 39.97, 116.451, 39.971)
    far = search_radius_m(116.0, 39.0, 117.0, 40.0)

    assert close == 1500
    assert far == 8000
    assert midpoint(116.0, 40.0, 118.0, 42.0) == (117.0, 41.0)
    assert centroid([(116.0, 40.0), (118.0, 42.0), (117.0, 41.0)]) == (117.0, 41.0)
    assert search_radius_from_points([(116.45, 39.97), (116.451, 39.971)]) == 1500
