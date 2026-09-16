"""酒店属性与一级床型筛选。

本文件按美团/携程常见一级筛选项，用店名和标签关键词识别温泉、电竞、独家、华住会等属性，以及大床房、双床房、家庭房、套房；不读取实时房态。
"""

from app.schemas import PoiRecord

HOTEL_PLACE_TYPE = "100000"

# 华住会常见门店名，长的品牌写在前面以免被短词误伤。
HUAZHU_BRANDS: tuple[str, ...] = (
    "桔子水晶",
    "宜必思尚品",
    "美仑美奂",
    "美仑国际",
    "花间堂",
    "施柏阁",
    "诺富特",
    "CitiGO",
    "citigo",
    "华住",
    "汉庭",
    "全季",
    "桔子",
    "漫心",
    "海友",
    "星程",
    "禧玥",
    "希岸",
    "宜必思",
    "美居",
    "美爵",
    "城际",
    "城家",
    "励业",
    "宋品",
)

HOTEL_ATTRS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("hotspring", "温泉", ("温泉",)),
    ("esports", "电竞", ("电竞", "电玩", "爱电竞", "雷神竞")),
    ("exclusive", "独家", ("独家",)),
    ("huazhu", "华住会", HUAZHU_BRANDS),
    ("parent_child", "亲子", ("亲子",)),
    ("homestay", "民宿", ("民宿",)),
)

HOTEL_BED_TYPES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("king", "大床房", ("大床房", "大床")),
    ("twin", "双床房", ("双床房", "双床", "双人床")),
    ("family", "家庭房", ("家庭房", "亲子房")),
    ("suite", "套房", ("套房",)),
)

# 额外关键词召回，用于把周边搜漏掉的主题店补进候选；命中后仍按店名/标签打标。
HOTEL_TEXT_QUERIES: tuple[str, ...] = (
    "温泉",
    "电竞",
    "独家",
    "汉庭",
    "全季",
    "大床房",
    "双床房",
    "家庭房",
    "套房",
)


def classify_hotel(record: PoiRecord) -> tuple[list[str], list[str]]:
    """从酒店 POI 店名和标签识别属性与一级床型。"""

    text = f"{record.name} {record.tag}"
    attrs = [key for key, _label, keywords in HOTEL_ATTRS if _contains_any(text, keywords)]
    beds = [key for key, _label, keywords in HOTEL_BED_TYPES if _contains_any(text, keywords)]
    return attrs, beds


def hotel_has_filter_signal(record: PoiRecord) -> bool:
    """判断该酒店能否进入主题/床型补召，避免把无关关键词结果混进列表。"""

    attrs, beds = classify_hotel(record)
    return bool(attrs or beds)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)
