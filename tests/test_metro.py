"""地铁线路解析与公交折线测试。

本文件验证线路名提取、通勤点范围过滤，以及高德公交/骑行规划结果转成地图折线。
"""

from app.metro import (
    clean_station_name,
    decode_polyline,
    fill_plan_stats,
    parse_all_transit_plans,
    parse_bus_line_payload,
    parse_line_names,
    parse_riding_payload,
    parse_transit_payload,
    plan_summary,
    select_metro_stations,
    to_metro_station,
)
from app.schemas import LocationResponse, MetroStation


def test_parse_line_names_from_address_and_busline() -> None:
    assert parse_line_names("10号线;13号线") == ["10号线", "13号线"]
    assert parse_line_names("地铁10号线(巴沟--苏州街)") == ["10号线"]
    assert parse_line_names("首都机场线", "大兴机场线") == ["首都机场线", "大兴机场线"]


def test_clean_station_name_strips_suffix() -> None:
    assert clean_station_name("知春路(地铁站)") == "知春路"
    assert clean_station_name("西土城（地铁站）") == "西土城"


def test_decode_polyline() -> None:
    assert decode_polyline("116.49,39.99;116.45,39.97") == [(116.49, 39.99), (116.45, 39.97)]
    assert decode_polyline("") == []


def test_select_metro_stations_keeps_points_between_origins() -> None:
    origins = [
        LocationResponse(lng=116.40, lat=39.96, formatted_address="A", city="北京"),
        LocationResponse(lng=116.49, lat=40.00, formatted_address="B", city="北京"),
    ]
    stations = [
        MetroStation(id="in", name="知春路", lng=116.45, lat=39.98, lines=["10号线"]),
        MetroStation(id="out", name="天安门东", lng=116.40, lat=39.91, lines=["1号线"]),
    ]

    selected = select_metro_stations(stations, origins, (116.445, 39.98))

    assert [item.id for item in selected] == ["in"]


def test_to_metro_station_parses_lines() -> None:
    station = to_metro_station("s1", "知春路(地铁站)", 116.45, 39.98, "10号线;13号线")

    assert station.name == "知春路"
    assert station.lines == ["10号线", "13号线"]


def test_parse_transit_payload_colors_subway_segment() -> None:
    payload = {
        "route": {
            "transits": [
                {
                    "duration": "1500",
                    "segments": [
                        {"walking": {"steps": [{"polyline": "116.49,39.99;116.488,39.988"}]}},
                        {
                            "bus": {
                                "buslines": [
                                    {
                                        "name": "地铁10号线(巴沟--苏州街)",
                                        "type": "地铁线路",
                                        "duration": "900",
                                        "polyline": "116.488,39.988;116.45,39.97",
                                        "departure_stop": {
                                            "name": "知春路",
                                            "id": "s1",
                                            "location": "116.488,39.988",
                                        },
                                        "via_stops": [
                                            {"name": "西土城", "id": "s3", "location": "116.46,39.98"}
                                        ],
                                        "arrival_stop": {
                                            "name": "芍药居",
                                            "id": "s2",
                                            "location": "116.45,39.97",
                                        },
                                    }
                                ]
                            }
                        },
                    ],
                }
            ]
        }
    }

    duration, segments = parse_transit_payload(payload)

    assert duration == 1500
    assert segments[0].mode == "WALK"
    assert segments[1].mode == "SUBWAY"
    assert segments[1].line == "10号线"
    assert [(item.lng, item.lat) for item in segments[1].path] == [(116.488, 39.988), (116.45, 39.97)]
    assert [item.name for item in segments[1].stations] == ["知春路", "西土城", "芍药居"]


def test_parse_all_transit_plans_keeps_multiple() -> None:
    payload = {
        "route": {
            "transits": [
                {
                    "duration": "1500",
                    "segments": [
                        {
                            "bus": {
                                "buslines": [
                                    {
                                        "name": "地铁10号线",
                                        "type": "地铁线路",
                                        "polyline": "116.48,39.98;116.45,39.97",
                                    }
                                ]
                            }
                        }
                    ],
                },
                {
                    "duration": "1800",
                    "segments": [
                        {
                            "bus": {
                                "buslines": [
                                    {
                                        "name": "地铁13号线",
                                        "type": "地铁线路",
                                        "polyline": "116.47,39.99;116.45,39.97",
                                    }
                                ]
                            }
                        }
                    ],
                },
            ]
        }
    }

    plans = parse_all_transit_plans(payload)

    assert [item.summary for item in plans] == ["10号线", "13号线"]
    assert plans[1].duration_s == 1800


def test_parse_bus_line_payload() -> None:
    line = parse_bus_line_payload(
        {
            "buslines": [
                {"name": "375路", "type": "公交线路", "polyline": "116.1,39.9;116.2,39.9"},
                {"name": "地铁10号线(巴沟--苏州街)", "type": "地铁线路", "polyline": "116.49,39.99;116.45,39.97"},
            ]
        },
        "10号线",
    )

    assert line is not None
    assert line.name == "10号线"
    assert len(line.path) == 2


def test_fill_plan_stats_splits_walk_metro_transfer() -> None:
    from app.schemas import RoutePoint, RouteSegment, TransitPlan

    path = [RoutePoint(lng=116.4500, lat=39.9700), RoutePoint(lng=116.4502, lat=39.9700)]
    plan = fill_plan_stats(
        TransitPlan(
            duration_s=1500,
            summary="10号线 → 13号线",
            segments=[
                RouteSegment(mode="WALK", duration_s=180, path=path),
                RouteSegment(mode="SUBWAY", line="10号线", duration_s=600, path=path),
                RouteSegment(mode="WALK", duration_s=120, path=path),
                RouteSegment(mode="SUBWAY", line="13号线", duration_s=480, path=path),
                RouteSegment(mode="WALK", duration_s=120, path=path),
            ],
        )
    )

    assert plan.walking_s == 420
    assert plan.metro_s == 1080
    assert plan.transfer_s == 120
    assert plan.transfer_count == 1
    assert plan.lastmile_mode == "WALK"
    assert plan.lastmile_s == 120
    assert [item.label for item in plan.legs] == ["步行到站", "10号线", "换乘步行", "13号线", "步行到店"]


def test_fill_plan_stats_converts_far_last_mile_to_riding() -> None:
    from app.schemas import RoutePoint, RouteSegment, TransitPlan

    short = [RoutePoint(lng=116.4500, lat=39.9700), RoutePoint(lng=116.4502, lat=39.9700)]
    far = [RoutePoint(lng=116.4500, lat=39.9700), RoutePoint(lng=116.4590, lat=39.9700)]
    plan = fill_plan_stats(
        TransitPlan(
            duration_s=1980,
            summary="10号线",
            segments=[
                RouteSegment(mode="WALK", duration_s=180, path=short),
                RouteSegment(mode="SUBWAY", line="10号线", duration_s=1200, path=short),
                RouteSegment(mode="WALK", duration_s=600, path=far),
            ],
        )
    )

    assert plan.lastmile_mode == "RIDING"
    assert plan.legs[-1].label == "骑行到店"
    assert plan.legs[-1].mode == "RIDING"
    assert plan.segments[-1].mode == "RIDING"
    assert plan.walking_s == 180
    assert plan.lastmile_s is not None and plan.lastmile_s < 600
    assert plan.duration_s is not None and plan.duration_s < 1980


def test_plan_summary_skips_walk() -> None:
    from app.schemas import RoutePoint, RouteSegment

    summary = plan_summary(
        [
            RouteSegment(mode="WALK", line="", path=[RoutePoint(lng=1, lat=1), RoutePoint(lng=2, lat=2)]),
            RouteSegment(mode="SUBWAY", line="10号线", path=[RoutePoint(lng=2, lat=2), RoutePoint(lng=3, lat=3)]),
            RouteSegment(mode="SUBWAY", line="13号线", path=[RoutePoint(lng=3, lat=3), RoutePoint(lng=4, lat=4)]),
        ]
    )

    assert summary == "10号线 → 13号线"


def test_chain_stations_as_line() -> None:
    from app.metro import chain_stations_as_line
    from app.schemas import MetroStation

    line = chain_stations_as_line(
        "10号线",
        [
            MetroStation(id="a", name="芍药居", lng=116.43, lat=39.97, lines=["10号线"]),
            MetroStation(id="b", name="太阳宫", lng=116.45, lat=39.97, lines=["10号线"]),
            MetroStation(id="c", name="西土城", lng=116.35, lat=39.97, lines=["10号线"]),
        ],
    )

    assert line is not None
    assert [round(item.lng, 2) for item in line.path] == [116.35, 116.43, 116.45]


def test_parse_riding_payload() -> None:
    payload = {
        "errcode": 0,
        "data": {"paths": [{"duration": "1200", "steps": [{"polyline": "116.49,39.99;116.45,39.97"}]}]},
    }

    duration, path = parse_riding_payload(payload)

    assert duration == 1200
    assert [(item.lng, item.lat) for item in path] == [(116.49, 39.99), (116.45, 39.97)]
