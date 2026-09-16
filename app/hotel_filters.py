"""酒店属性与一级床型筛选。

本文件用店名/标签识别温泉、电竞、独家、华住会等属性；一级床型由携程该店房型名称归类，不再用店名里的「大床房」字样冒充在售房型。
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

# 额外关键词召回主题店；床型不再按店名补召。
HOTEL_TEXT_QUERIES: tuple[str, ...] = (
    "温泉",
    "电竞",
    "独家",
    "汉庭",
    "全季",
)


def classify_hotel(record: PoiRecord) -> tuple[list[str], list[str]]:
    """从酒店 POI 店名和标签识别属性；床型留给携程房型列表。"""

    text = f"{record.name} {record.tag}"
    attrs = [key for key, _label, keywords in HOTEL_ATTRS if _contains_any(text, keywords)]
    return attrs, []


def classify_bed_types(room_names: list[str]) -> list[str]:
    """把携程该店房型名称归类为一级床型。"""

    text = " ".join(room_names)
    return [key for key, _label, keywords in HOTEL_BED_TYPES if _contains_any(text, keywords)]


def hotel_has_filter_signal(record: PoiRecord) -> bool:
    """判断该酒店能否进入主题补召，避免把无关关键词结果混进列表。"""

    attrs, _beds = classify_hotel(record)
    return bool(attrs)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)
