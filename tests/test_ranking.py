"""扫街榜分类配置测试。

本文件验证2026状元榜六类的搭配推荐和网页榜单路径。
"""

from app.open_links import amap_ranking_url
from app.ranking import companion_category, ranking_kind_for


def test_companion_pairs_food_with_play() -> None:
    assert companion_category("restaurant") == "play"
    assert companion_category("coffee") == "play"
    assert companion_category("play") == "restaurant"
    assert companion_category("scenic") == "restaurant"
    assert companion_category("hotel") is None


def test_ranking_kind_uses_confirmed_web_paths() -> None:
    assert ranking_kind_for("scenic") == "scenic"
    assert ranking_kind_for("hotel") == "hotel"
    assert ranking_kind_for("play") == "food"
    assert amap_ranking_url("北京", ranking_kind_for("scenic")).endswith("/scenic")
