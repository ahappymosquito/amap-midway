"""酒店属性与一级床型筛选测试。

本文件验证温泉、电竞、独家、华住会等标签和一级床型只按店名/标签命中，不把无关关键词结果算进去。
"""

from app.hotel_filters import classify_hotel, hotel_has_filter_signal
from app.schemas import PoiRecord


def _record(name: str, tag: str = "") -> PoiRecord:
    return PoiRecord(id="x", name=name, lng=116.45, lat=39.98, tag=tag)


def test_classify_hotspring_esports_exclusive_and_huazhu() -> None:
    assert classify_hotel(_record("朗丽兹温泉酒店"))[0] == ["hotspring"]
    assert classify_hotel(_record("雷神电竞酒店"))[0] == ["esports"]
    assert classify_hotel(_record("美团独家精选酒店"))[0] == ["exclusive"]
    assert classify_hotel(_record("汉庭酒店(望京店)"))[0] == ["huazhu"]
    assert classify_hotel(_record("桔子水晶酒店(中关村店)"))[0] == ["huazhu"]
    assert classify_hotel(_record("全季酒店(北京昌平小汤山温泉度假区店)"))[0] == ["hotspring", "huazhu"]


def test_classify_parent_child_homestay_and_bed_types() -> None:
    assert classify_hotel(_record("亲子主题民宿")) == (["parent_child", "homestay"], [])
    assert classify_hotel(_record("亲子房民宿")) == (["parent_child", "homestay"], ["family"])
    assert classify_hotel(_record("雅致大床房酒店"))[1] == ["king"]
    assert classify_hotel(_record("商务双床房酒店"))[1] == ["twin"]
    assert classify_hotel(_record("望京商务套房酒店"))[1] == ["suite"]
    assert classify_hotel(_record("皇冠假日")) == ([], [])


def test_unrelated_keyword_hit_is_not_a_filter_signal() -> None:
    decoy = _record("顺业精品酒店")
    assert hotel_has_filter_signal(decoy) is False
    assert hotel_has_filter_signal(_record("WD电竞酒店")) is True
