"""外链生成模块。

本文件按城市和品类生成高德、美团、携程、点评和扫街榜网页链接：酒店走美团酒店 H5 与携程 searchWord 列表，餐馆走美团到餐页。
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from app.schemas import OpenLinks

CHINA_TZ = timezone(timedelta(hours=8))

# 携程国内城市 ID（与 hotels.ctrip.com 的 cityId 一致）
CTRIP_CITY_IDS = {
    "北京": 1,
    "上海": 2,
    "天津": 3,
    "重庆": 4,
    "哈尔滨": 5,
    "大连": 6,
    "青岛": 7,
    "西安": 10,
    "宁波": 11,
    "南京": 12,
    "无锡": 13,
    "苏州": 14,
    "扬州": 15,
    "杭州": 17,
    "厦门": 25,
    "成都": 28,
    "深圳": 30,
    "珠海": 31,
    "广州": 32,
    "桂林": 33,
    "昆明": 34,
    "贵阳": 38,
    "乌鲁木齐": 39,
    "拉萨": 41,
    "海口": 42,
    "三亚": 43,
    "太原": 105,
    "济南": 144,
    "长春": 158,
    "南宁": 167,
    "长沙": 206,
    "常州": 207,
    "佛山": 209,
    "东莞": 223,
    "福州": 258,
    "合肥": 278,
    "呼和浩特": 321,
    "南昌": 376,
    "石家庄": 428,
    "沈阳": 451,
    "武汉": 477,
    "温州": 491,
    "郑州": 559,
}

CTRIP_PROVINCE_IDS = {"北京": 1, "上海": 2, "天津": 3, "重庆": 4}

# 美团城市 ID（酒店 H5 cityId / 到餐 ci）
MEITUAN_CITY_IDS = {
    "北京": 1,
    "上海": 10,
    "广州": 20,
    "深圳": 30,
    "天津": 40,
    "西安": 42,
    "福州": 44,
    "重庆": 45,
    "杭州": 50,
    "宁波": 51,
    "无锡": 52,
    "南京": 55,
    "合肥": 56,
    "武汉": 57,
    "成都": 59,
    "青岛": 60,
    "厦门": 62,
    "大连": 65,
    "沈阳": 66,
    "长沙": 70,
    "郑州": 73,
    "哈尔滨": 75,
    "石家庄": 76,
    "苏州": 80,
    "南昌": 83,
    "长春": 84,
    "南宁": 99,
    "太原": 101,
    "兰州": 103,
    "贵阳": 107,
    "呼和浩特": 111,
    "昆明": 114,
    "海口": 94,
    "济南": 96,
    "乌鲁木齐": 92,
    "东莞": 91,
    "佛山": 208,
    "珠海": 108,
}

# 大众点评城市 ID（北京是 2，上海是 1）
DIANPING_CITY_IDS = {
    "上海": 1,
    "北京": 2,
    "杭州": 3,
    "广州": 4,
    "南京": 5,
    "苏州": 6,
    "深圳": 7,
    "成都": 8,
    "重庆": 9,
    "天津": 10,
    "宁波": 11,
    "福州": 14,
    "厦门": 15,
    "武汉": 16,
    "西安": 17,
    "青岛": 21,
    "济南": 22,
    "大连": 19,
    "沈阳": 18,
    "长沙": 344,
    "郑州": 160,
    "合肥": 110,
    "昆明": 267,
    "哈尔滨": 25,
    "长春": 70,
    "石家庄": 24,
    "南昌": 212,
    "南宁": 380,
    "太原": 26,
}

# 高德扫街榜网页城市路径，对应 www.amap.com/ranking/{slug}
AMAP_RANKING_SLUGS = {
    "北京": "beijing",
    "上海": "shanghai",
    "广州": "guangzhou",
    "深圳": "shenzhen",
    "杭州": "hangzhou",
    "南京": "nanjing",
    "成都": "chengdu",
    "武汉": "wuhan",
    "西安": "xian",
    "重庆": "chongqing",
    "天津": "tianjin",
    "苏州": "suzhou",
    "长沙": "changsha",
    "郑州": "zhengzhou",
    "青岛": "qingdao",
    "厦门": "xiamen",
    "宁波": "ningbo",
    "无锡": "wuxi",
    "合肥": "hefei",
    "福州": "fuzhou",
    "济南": "jinan",
    "沈阳": "shenyang",
    "大连": "dalian",
    "昆明": "kunming",
    "哈尔滨": "haerbin",
    "长春": "changchun",
    "石家庄": "shijiazhuang",
    "南昌": "nanchang",
    "南宁": "nanning",
    "太原": "taiyuan",
    "贵阳": "guiyang",
    "海口": "haikou",
    "兰州": "lanzhou",
    "东莞": "dongguan",
    "佛山": "foshan",
    "珠海": "zhuhai",
    "三亚": "sanya",
}


def build_open_links(
    *,
    name: str,
    lng: float,
    lat: float,
    category: str,
    poi_id: str = "",
    city: str = "",
) -> OpenLinks:
    """生成指定地点在高德、美团、携程、点评的打开链接。"""

    city_name = plain_city(city)
    encoded_name = quote(name)
    amap = (
        f"https://uri.amap.com/marker?position={lng:.6f},{lat:.6f}"
        f"&name={encoded_name}&src=amap_find&coordinate=gaode&callnative=0"
    )
    if poi_id:
        amap_app = f"amapuri://poi/detail?src=amap_find&poiid={quote(poi_id)}"
    else:
        amap_app = (
            "amapuri://viewMap?sourceApplication=amap_find"
            f"&poiname={encoded_name}&lat={lat:.6f}&lon={lng:.6f}&dev=0"
        )
    meituan_city_id = MEITUAN_CITY_IDS.get(city_name, 1)
    checkin, checkout = _stay_dates()
    if category == "hotel":
        meituan = _meituan_hotel_url(name, meituan_city_id, lng, lat, checkin, checkout)
        ctrip = _ctrip_hotel_url(name, city_name, checkin, checkout)
        dianping = None
    else:
        meituan = f"https://meishi.meituan.com/i/?ci={meituan_city_id}&q={encoded_name}"
        ctrip = None
        dianping_city_id = DIANPING_CITY_IDS.get(city_name, 2)
        dianping = f"https://www.dianping.com/search/keyword/{dianping_city_id}/10_{encoded_name}"
    return OpenLinks(
        amap=amap,
        amap_app=amap_app,
        meituan=meituan,
        meituan_app=f"imeituan://www.meituan.com/search?q={encoded_name}&ci={meituan_city_id}",
        ctrip=ctrip,
        dianping=dianping,
        amap_board=amap_ranking_url(city_name, "hotel" if category == "hotel" else "food"),
    )


def amap_ranking_url(city: str, kind: str = "food") -> str:
    """生成高德扫街榜网页地址：美食状元榜、烟火小店或必住酒店。"""

    slug = AMAP_RANKING_SLUGS.get(plain_city(city), "beijing")
    if kind == "hotel":
        return f"https://www.amap.com/ranking/{slug}/hotel"
    if kind == "shop":
        return f"https://www.amap.com/ranking/{slug}/shop"
    if kind == "select":
        return f"https://www.amap.com/ranking/{slug}/select-food"
    return f"https://www.amap.com/ranking/{slug}"


def plain_city(city: str) -> str:
    """把“北京市”这类行政区名收成城市短名。"""

    text = (city or "").strip()
    for suffix in ("特别行政区", "维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "省", "市"):
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
            break
    return text or "北京"


def _meituan_hotel_url(name: str, city_id: int, lng: float, lat: float, checkin: str, checkout: str) -> str:
    query = urlencode(
        {
            "cityId": city_id,
            "q": name,
            "checkIn": checkin,
            "checkOut": checkout,
            "lat": f"{lat:.6f}",
            "lng": f"{lng:.6f}",
        }
    )
    return f"https://i.meituan.com/awp/h5/hotel/list/list.html?{query}"


def _ctrip_hotel_url(name: str, city_name: str, checkin: str, checkout: str) -> str:
    city_id = CTRIP_CITY_IDS.get(city_name, 1)
    params: dict[str, str | int] = {
        "flexType": 1,
        "cityId": city_id,
        "countryId": 1,
        "cityName": city_name,
        "destName": city_name,
        "searchWord": name,
        "checkin": checkin,
        "checkout": checkout,
        "crn": 1,
        "directSearch": 1,
        "old": 1,
        "curr": "CNY",
        "locale": "zh-CN",
    }
    province_id = CTRIP_PROVINCE_IDS.get(city_name)
    if province_id:
        params["provinceId"] = province_id
    return f"https://hotels.ctrip.com/hotels/list?{urlencode(params)}"


def _stay_dates() -> tuple[str, str]:
    today = datetime.now(CHINA_TZ).date()
    return today.isoformat(), (today + timedelta(days=1)).isoformat()
