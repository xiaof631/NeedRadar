"""候选需求业务逻辑。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from app.db.storage import db
from app.models import CandidateNeed, CandidateNeedStatus, CandidateNeedStatusLog
from app.services.raw_entries import RawEntryNotFoundError


class CandidateNeedNotFoundError(Exception):
    """候选需求不存在。"""


class InvalidStatusTransitionError(Exception):
    """状态流转不符合预设的状态机。"""

    def __init__(
        self,
        current_status: CandidateNeedStatus,
        target_status: CandidateNeedStatus,
    ) -> None:
        self.current_status = current_status
        self.target_status = target_status
        message = (
            f"状态 {current_status.value} 无法流转至 {target_status.value}"
        )
        super().__init__(message)


_ALLOWED_STATUS_TRANSITIONS: dict[CandidateNeedStatus, tuple[CandidateNeedStatus, ...]] = {
    CandidateNeedStatus.PENDING_REVIEW: (
        CandidateNeedStatus.APPROVED,
        CandidateNeedStatus.REJECTED,
    ),
    CandidateNeedStatus.APPROVED: (
        CandidateNeedStatus.IN_DISCOVERY,
        CandidateNeedStatus.REJECTED,
    ),
    CandidateNeedStatus.REJECTED: (
        CandidateNeedStatus.PENDING_REVIEW,
    ),
    CandidateNeedStatus.IN_DISCOVERY: (
        CandidateNeedStatus.COMPLETED,
        CandidateNeedStatus.REJECTED,
    ),
    CandidateNeedStatus.COMPLETED: (
        CandidateNeedStatus.IN_DISCOVERY,
    ),
}


def _ensure_raw_entry_exists(raw_entry_id: int) -> None:
    if db.get_raw_entry(raw_entry_id) is None:
        raise RawEntryNotFoundError


def _validate_status_transition(
    current: CandidateNeedStatus, target: CandidateNeedStatus
) -> None:
    if current == target:
        return
    allowed = _ALLOWED_STATUS_TRANSITIONS.get(current, tuple())
    if target not in allowed:
        raise InvalidStatusTransitionError(current, target)


def create_need(data: dict[str, Any]) -> CandidateNeed:
    """创建候选需求。"""

    _ensure_raw_entry_exists(data["raw_entry_id"])
    need = db.create_candidate_need(data)
    _record_status_transition(need.id, None, need.status)
    return need


def update_need(need_id: int, data: dict[str, Any]) -> CandidateNeed:
    """更新候选需求信息。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError
    if "raw_entry_id" in data:
        _ensure_raw_entry_exists(data["raw_entry_id"])
    previous_status = need.status

    if "status" in data and data["status"] is not None:
        _validate_status_transition(previous_status, data["status"])

    def _apply(model: CandidateNeed) -> None:
        for key, value in data.items():
            setattr(model, key, value)

    updated = db.update_candidate_need(need_id, _apply)
    if "status" in data and updated.status != previous_status:
        _record_status_transition(updated.id, previous_status, updated.status)
    return updated


def update_need_status(need_id: int, status: CandidateNeedStatus) -> CandidateNeed:
    """更新候选需求状态。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError
    previous_status = need.status
    _validate_status_transition(previous_status, status)

    def _apply(model: CandidateNeed) -> None:
        model.status = status

    updated = db.update_candidate_need(need_id, _apply)
    if previous_status != status:
        _record_status_transition(need_id, previous_status, status)
    return updated


def get_need(need_id: int) -> CandidateNeed:
    """获取候选需求详情。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError
    return need


def get_need_by_raw_entry(raw_entry_id: int) -> CandidateNeed | None:
    """根据原始条目 ID 查找候选需求。"""

    return db.get_candidate_need_by_raw_entry(raw_entry_id)


def delete_need(need_id: int) -> None:
    """删除候选需求。"""

    if db.get_candidate_need(need_id) is None:
        raise CandidateNeedNotFoundError
    db.delete_candidate_need(need_id)


def list_need_status_logs(need_id: int) -> list[CandidateNeedStatusLog]:
    """返回候选需求的状态流转记录。"""

    if db.get_candidate_need(need_id) is None:
        raise CandidateNeedNotFoundError
    return db.list_candidate_need_logs(need_id)


def list_needs(
    *,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    search: str | None = None,
    raw_entry_id: int | None = None,
    synced: bool | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[CandidateNeed]]:
    """列出候选需求。"""

    items = db.list_candidate_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        synced=synced,
        skip=skip,
        limit=limit,
    )
    total = db.count_candidate_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        synced=synced,
    )
    return total, items


def export_needs(
    *,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    search: str | None = None,
    raw_entry_id: int | None = None,
    synced: bool | None = None,
    limit: int | None = None,
) -> list[CandidateNeed]:
    """导出候选需求列表。"""

    _, items = list_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        synced=synced,
        skip=0,
        limit=limit,
    )
    return items


def list_unsynced_needs(
    *,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    limit: int | None = None,
) -> list[CandidateNeed]:
    """返回尚未推送至下游的候选需求。"""

    _, items = list_needs(
        statuses=statuses,
        synced=False,
        limit=limit,
    )
    return items


def mark_need_synced(need_id: int) -> CandidateNeed:
    """记录候选需求已成功同步。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError

    timestamp = datetime.now(UTC)

    def _apply(model: CandidateNeed) -> None:
        model.synced_at = timestamp
        model.sync_error = None

    return db.update_candidate_need(need_id, _apply)


def mark_need_sync_failed(need_id: int, error: str | None = None) -> CandidateNeed:
    """记录候选需求同步失败的原因。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError

    def _apply(model: CandidateNeed) -> None:
        model.sync_error = error
        model.synced_at = None

    return db.update_candidate_need(need_id, _apply)


def reset_storage() -> None:
    """测试辅助函数：清空内存数据。"""

    db.reset()


def _record_status_transition(
    need_id: int,
    from_status: CandidateNeedStatus | None,
    to_status: CandidateNeedStatus,
    note: str | None = None,
) -> CandidateNeedStatusLog:
    return db.add_candidate_need_log(
        need_id,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )
