"""外链生成模块。

本文件根据 POI 名称、坐标、品类和高德 ID 生成高德、美团、携程、点评的网页与 App 跳转链接，供前端一键看价。
"""

from urllib.parse import quote

from app.schemas import OpenLinks


def build_open_links(*, name: str, lng: float, lat: float, category: str, poi_id: str = "") -> OpenLinks:
    """生成指定地点在高德、美团、携程、点评的打开链接。"""

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
    return OpenLinks(
        amap=amap,
        amap_app=amap_app,
        meituan=f"https://www.meituan.com/s/{encoded_name}",
        meituan_app=f"imeituan://www.meituan.com/search?q={encoded_name}",
        ctrip=f"https://hotels.ctrip.com/hotels/list?keyword={encoded_name}" if category == "hotel" else None,
        dianping=f"https://www.dianping.com/search/keyword/0/0_{encoded_name}" if category == "restaurant" else None,
    )
