"""差标判断模块。

本文件按一人 300、两人合计 600 的默认差标，判断餐馆人均或酒店参考价是否超标。
"""

from app.schemas import PlaceCategory

DEFAULT_BUDGET_PER_PERSON = 300


def couple_budget(budget_per_person: int, people_count: int = 2) -> int:
    """总差标为单人额度按人数叠加。"""

    return budget_per_person * people_count


def is_over_budget(
    category: PlaceCategory,
    cost: float | None,
    budget_per_person: int,
    people_count: int = 2,
) -> bool:
    """已知价格时判断是否超标；无价格则不标超标，由前端提示去网页核价。"""

    if cost is None:
        return False
    if category == "hotel":
        return cost > couple_budget(budget_per_person, people_count)
    return cost > budget_per_person
