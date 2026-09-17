"""地点名单解析测试。

本文件验证分行、中英文分号导入，以及去重和上限。
"""

from app.place_names import parse_place_names


def test_parse_place_names_splits_newlines_and_semicolons() -> None:
    text = "望京SOHO\n北控水务大厦；中国黄金大厦; 三里屯"
    assert parse_place_names(text) == ["望京SOHO", "北控水务大厦", "中国黄金大厦", "三里屯"]


def test_parse_place_names_skips_blank_and_duplicates() -> None:
    text = "望京SOHO；\n望京SOHO；  望京SOHO  "
    assert parse_place_names(text) == ["望京SOHO"]


def test_parse_place_names_respects_limit() -> None:
    text = "；".join(f"地点{index}" for index in range(1, 10))
    assert parse_place_names(text, limit=6) == [f"地点{index}" for index in range(1, 7)]
