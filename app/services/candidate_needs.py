"""候选需求业务逻辑。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from app.db.storage import db
from app.models import (
    CandidateNeed,
    CandidateNeedStatus,
    CandidateNeedStatusLog,
    CandidateNeedType,
    SourceType,
)
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

_BUG_MARKERS = (
    " bug",
    "[bug]",
    "error",
    "errors",
    "failed",
    "fail ",
    "failing",
    "crash",
    "crashes",
    "stuck",
    "not working",
    "typeerror",
    "oauth",
    "invalid",
    "500",
    "outage",
    "down",
    "无法使用",
    "崩了",
    "卡死",
)
_FEATURE_GAP_MARKERS = (
    "missing",
    "cannot",
    "unable",
    "hardcoded",
    "lack",
    "needs",
    "need support",
    "should support",
    "feature",
    "capability",
    "不支持",
    "缺少",
)
_TOOL_SEEKING_MARKERS = (
    "looking for",
    "recommend",
    "alternative",
    "replacement",
    "switch from",
    "switched from",
    "what do you use",
    "which",
    "求推荐",
    "推荐",
    "替代",
    "渠道",
)
_WORKFLOW_PAIN_MARKERS = (
    "manual",
    "workflow",
    "offline",
    "friction",
    "pain",
    "painful",
    "spreadsheet",
    "tedious",
    "slow",
    "ops",
    "记事本",
    "碎片",
    "繁琐",
    "低效",
    "痛点",
    "停摆",
)
_REVIEW_READY_THRESHOLD = 0.55


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

    raw_entry_id = data["raw_entry_id"]
    _ensure_raw_entry_exists(raw_entry_id)
    payload = _enrich_need_payload(data, raw_entry_id=raw_entry_id)
    need = db.create_candidate_need(payload)
    _record_status_transition(need.id, None, need.status)
    return need


def update_need(need_id: int, data: dict[str, Any]) -> CandidateNeed:
    """更新候选需求信息。"""

    need = db.get_candidate_need(need_id)
    if need is None:
        raise CandidateNeedNotFoundError
    raw_entry_id = data.get("raw_entry_id", need.raw_entry_id)
    if "raw_entry_id" in data:
        _ensure_raw_entry_exists(raw_entry_id)
    previous_status = need.status

    payload = dict(data)
    if _should_refresh_review_metadata(payload):
        payload = _enrich_need_payload(payload, raw_entry_id=raw_entry_id, existing=need)

    if "status" in payload and payload["status"] is not None:
        _validate_status_transition(previous_status, payload["status"])

    def _apply(model: CandidateNeed) -> None:
        for key, value in payload.items():
            setattr(model, key, value)

    updated = db.update_candidate_need(need_id, _apply)
    if "status" in payload and updated.status != previous_status:
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
    source_type: SourceType | None = None,
    candidate_type: CandidateNeedType | None = None,
    min_review_readiness: float | None = None,
    review_ready_only: bool | None = None,
    synced: bool | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[CandidateNeed]]:
    """列出候选需求。"""

    items = db.list_candidate_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        source_type=source_type,
        candidate_type=candidate_type,
        min_review_readiness=min_review_readiness,
        review_ready_only=review_ready_only,
        synced=synced,
        skip=skip,
        limit=limit,
    )
    total = db.count_candidate_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        source_type=source_type,
        candidate_type=candidate_type,
        min_review_readiness=min_review_readiness,
        review_ready_only=review_ready_only,
        synced=synced,
    )
    return total, items


def export_needs(
    *,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    search: str | None = None,
    raw_entry_id: int | None = None,
    source_type: SourceType | None = None,
    candidate_type: CandidateNeedType | None = None,
    min_review_readiness: float | None = None,
    review_ready_only: bool | None = None,
    synced: bool | None = None,
    limit: int | None = None,
) -> list[CandidateNeed]:
    """导出候选需求列表。"""

    _, items = list_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        source_type=source_type,
        candidate_type=candidate_type,
        min_review_readiness=min_review_readiness,
        review_ready_only=review_ready_only,
        synced=synced,
        skip=0,
        limit=limit,
    )
    return items


def list_unsynced_needs(
    *,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    source_type: SourceType | None = None,
    candidate_type: CandidateNeedType | None = None,
    min_review_readiness: float | None = None,
    review_ready_only: bool | None = None,
    limit: int | None = None,
) -> list[CandidateNeed]:
    """返回尚未推送至下游的候选需求。"""

    _, items = list_needs(
        statuses=statuses,
        source_type=source_type,
        candidate_type=candidate_type,
        min_review_readiness=min_review_readiness,
        review_ready_only=review_ready_only,
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


def refresh_review_metadata(need_id: int) -> CandidateNeed:
    """重新计算候选需求的类型与评审就绪度。"""

    need = get_need(need_id)
    payload = _enrich_need_payload({}, raw_entry_id=need.raw_entry_id, existing=need)
    return update_need(
        need_id,
        {
            "candidate_type": payload["candidate_type"],
            "review_readiness": payload["review_readiness"],
        },
    )


def refresh_all_review_metadata() -> int:
    """批量刷新所有候选需求的类型与评审就绪度。"""

    _, needs = list_needs(limit=5000)
    refreshed = 0
    for need in needs:
        refresh_review_metadata(need.id)
        refreshed += 1
    return refreshed


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


def _should_refresh_review_metadata(data: dict[str, Any]) -> bool:
    tracked_fields = {
        "raw_entry_id",
        "summary",
        "problem_statement",
        "target_users",
        "value_proposition",
        "competition",
        "confidence",
        "rule_score",
        "candidate_type",
        "review_readiness",
    }
    return any(field in data for field in tracked_fields)


def _enrich_need_payload(
    data: dict[str, Any],
    *,
    raw_entry_id: int,
    existing: CandidateNeed | None = None,
) -> dict[str, Any]:
    payload = dict(data)
    summary = str(payload.get("summary", existing.summary if existing else "") or "")
    problem_statement = payload.get(
        "problem_statement",
        existing.problem_statement if existing else None,
    )
    value_proposition = payload.get(
        "value_proposition",
        existing.value_proposition if existing else None,
    )
    confidence = payload.get("confidence", existing.confidence if existing else None)
    rule_score = payload.get("rule_score", existing.rule_score if existing else None)
    raw_entry = db.get_raw_entry(raw_entry_id)
    source = db.get_source(raw_entry.source_id) if raw_entry is not None else None
    candidate_type = payload.get("candidate_type")
    if candidate_type is None:
        candidate_type = _classify_candidate_type(
            summary=summary,
            problem_statement=problem_statement,
            value_proposition=value_proposition,
            source_type=source.source_type if source else None,
        )
    review_readiness = payload.get("review_readiness")
    if review_readiness is None:
        review_readiness = _estimate_review_readiness(
            candidate_type=candidate_type,
            summary=summary,
            problem_statement=problem_statement,
            source_type=source.source_type if source else None,
            confidence=confidence,
            rule_score=rule_score,
        )
    payload["candidate_type"] = candidate_type
    payload["review_readiness"] = review_readiness
    return payload


def _classify_candidate_type(
    *,
    summary: str,
    problem_statement: str | None,
    value_proposition: str | None,
    source_type: SourceType | None,
) -> CandidateNeedType:
    text = "\n".join(part for part in (summary, problem_statement, value_proposition) if part).lower()
    if source_type == SourceType.GITHUB_ISSUES:
        if any(marker in text for marker in _BUG_MARKERS):
            return CandidateNeedType.BUG_REPORT
        if any(marker in text for marker in _FEATURE_GAP_MARKERS):
            return CandidateNeedType.FEATURE_GAP
    if any(marker in text for marker in _TOOL_SEEKING_MARKERS):
        return CandidateNeedType.TOOL_SEEKING
    if any(marker in text for marker in _WORKFLOW_PAIN_MARKERS):
        return CandidateNeedType.WORKFLOW_PAIN
    if any(marker in text for marker in _FEATURE_GAP_MARKERS):
        return CandidateNeedType.FEATURE_GAP
    if any(marker in text for marker in _BUG_MARKERS):
        return CandidateNeedType.BUG_REPORT
    return CandidateNeedType.MARKET_SIGNAL


def _estimate_review_readiness(
    *,
    candidate_type: CandidateNeedType,
    summary: str,
    problem_statement: str | None,
    source_type: SourceType | None,
    confidence: float | None,
    rule_score: float | None,
) -> float:
    base = {
        CandidateNeedType.WORKFLOW_PAIN: 0.74,
        CandidateNeedType.FEATURE_GAP: 0.62,
        CandidateNeedType.TOOL_SEEKING: 0.58,
        CandidateNeedType.MARKET_SIGNAL: 0.48,
        CandidateNeedType.BUG_REPORT: 0.28,
    }[candidate_type]
    text = "\n".join(part for part in (summary, problem_statement) if part).lower()
    if candidate_type == CandidateNeedType.BUG_REPORT and source_type != SourceType.GITHUB_ISSUES:
        base += 0.1
    if candidate_type in {CandidateNeedType.WORKFLOW_PAIN, CandidateNeedType.FEATURE_GAP}:
        if any(marker in text for marker in ("offline", "manual", "workflow", "painful", "停摆", "繁琐", "低效")):
            base += 0.06
    if candidate_type == CandidateNeedType.TOOL_SEEKING and any(
        marker in text for marker in ("alternative", "replacement", "求推荐", "推荐", "which")
    ):
        base += 0.04
    if isinstance(rule_score, float):
        base += max(-0.06, min(0.12, (rule_score - 0.45) * 0.35))
    if isinstance(confidence, float):
        base += max(-0.05, min(0.1, (confidence - 0.6) * 0.3))
    return round(max(0.0, min(0.99, base)), 2)


def is_review_ready(need: CandidateNeed) -> bool:
    """判断候选需求是否应默认进入评审队列。"""

    return (
        need.candidate_type is not CandidateNeedType.BUG_REPORT
        and (need.review_readiness or 0.0) >= _REVIEW_READY_THRESHOLD
    )
