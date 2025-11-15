"""筛选规则业务逻辑。"""

from __future__ import annotations

from typing import Any

from app.db.storage import db
from app.models import FilterRule


class FilterRuleNotFoundError(Exception):
    """筛选规则不存在。"""


def _normalize_collections(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.copy()
    if "keywords" in payload:
        values = payload["keywords"]
        payload["keywords"] = tuple(values or [])
    if "patterns" in payload:
        values = payload["patterns"]
        payload["patterns"] = tuple(values or [])
    return payload


def create_rule(data: dict[str, Any]) -> FilterRule:
    """创建新的筛选规则。"""

    payload = _normalize_collections(data)
    return db.create_filter_rule(payload)


def update_rule(rule_id: int, data: dict[str, Any]) -> FilterRule:
    """更新筛选规则。"""

    rule = db.get_filter_rule(rule_id)
    if rule is None:
        raise FilterRuleNotFoundError

    payload = _normalize_collections(data)

    def _apply(model: FilterRule) -> None:
        for key, value in payload.items():
            setattr(model, key, value)

    return db.update_filter_rule(rule_id, _apply)


def delete_rule(rule_id: int) -> None:
    """删除筛选规则。"""

    if db.get_filter_rule(rule_id) is None:
        raise FilterRuleNotFoundError
    db.delete_filter_rule(rule_id)


def get_rule(rule_id: int) -> FilterRule:
    """获取筛选规则详情。"""

    rule = db.get_filter_rule(rule_id)
    if rule is None:
        raise FilterRuleNotFoundError
    return rule


def list_rules(
    *,
    enabled: bool | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[FilterRule]]:
    """列出筛选规则，支持过滤。"""

    items = db.list_filter_rules(
        enabled=enabled,
        search=search,
        skip=skip,
        limit=limit,
    )
    total = db.count_filter_rules(enabled=enabled, search=search)
    return total, items


def reset_storage() -> None:
    """测试环境下清空数据。"""

    db.reset()
