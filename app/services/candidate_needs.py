"""候选需求业务逻辑。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.db.storage import db
from app.models import CandidateNeed, CandidateNeedStatus
from app.services.raw_entries import RawEntryNotFoundError


class CandidateNeedNotFoundError(Exception):
    """候选需求不存在。"""


def _ensure_raw_entry_exists(raw_entry_id: int) -> None:
    if db.get_raw_entry(raw_entry_id) is None:
        raise RawEntryNotFoundError


def create_need(data: dict[str, Any]) -> CandidateNeed:
    """创建候选需求。"""

    _ensure_raw_entry_exists(data["raw_entry_id"])
    return db.create_candidate_need(data)


def update_need(need_id: int, data: dict[str, Any]) -> CandidateNeed:
    """更新候选需求信息。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError
    if "raw_entry_id" in data:
        _ensure_raw_entry_exists(data["raw_entry_id"])

    def _apply(model: CandidateNeed) -> None:
        for key, value in data.items():
            setattr(model, key, value)

    return db.update_candidate_need(need_id, _apply)


def update_need_status(need_id: int, status: CandidateNeedStatus) -> CandidateNeed:
    """更新候选需求状态。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError

    def _apply(model: CandidateNeed) -> None:
        model.status = status

    return db.update_candidate_need(need_id, _apply)


def get_need(need_id: int) -> CandidateNeed:
    """获取候选需求详情。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError
    return need


def delete_need(need_id: int) -> None:
    """删除候选需求。"""

    if db.get_candidate_need(need_id) is None:
        raise CandidateNeedNotFoundError
    db.delete_candidate_need(need_id)


def list_needs(
    *,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    search: str | None = None,
    raw_entry_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[CandidateNeed]]:
    """列出候选需求。"""

    items = db.list_candidate_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        skip=skip,
        limit=limit,
    )
    total = db.count_candidate_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
    )
    return total, items


def export_needs(
    *,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    search: str | None = None,
    raw_entry_id: int | None = None,
    limit: int | None = None,
) -> list[CandidateNeed]:
    """导出候选需求列表。"""

    _, items = list_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        skip=0,
        limit=limit,
    )
    return items


def reset_storage() -> None:
    """测试辅助函数：清空内存数据。"""

    db.reset()
