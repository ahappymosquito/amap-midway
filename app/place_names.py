"""地点名单解析。

本文件把粘贴或导入的文本按换行、中英文分号拆成去重后的地点名，供前端批量填入通勤点。
"""

import re

PLACE_NAME_SPLIT = re.compile(r"[\n\r；;]+")
DEFAULT_PLACE_LIMIT = 6


def parse_place_names(text: str, limit: int = DEFAULT_PLACE_LIMIT) -> list[str]:
    """按换行或分号拆地点名，去掉空白和重复，最多保留 limit 个。"""

    names: list[str] = []
    seen: set[str] = set()
    for part in PLACE_NAME_SPLIT.split(text or ""):
        name = part.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names
