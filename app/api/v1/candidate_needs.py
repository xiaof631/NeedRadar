"""候选需求 API。"""

# ruff: noqa: I001
from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import asdict
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, status

from app.db.storage import db
from app.models import CandidateNeed, CandidateNeedStatus, CandidateNeedType, ExportJobStatus, RssSource, SourceType, SyncChannel
from app.schemas import (
    CandidateNeedClusterList,
    CandidateNeedClusterRead,
    CandidateNeedExportJobCreate,
    CandidateNeedExportJobRead,
    CandidateNeedExportJobList,
    CandidateNeedCreate,
    CandidateNeedList,
    CandidateNeedRead,
    CandidateNeedStatusLogRead,
    CandidateNeedStatusEnum,
    CandidateNeedStatusUpdate,
    CandidateNeedTypeEnum,
    CandidateNeedSyncLogList,
    CandidateNeedSyncLogRead,
    CandidateNeedSyncChannelStat,
    CandidateNeedUpdate,
    SyncChannelEnum,
)
import app.services.export_jobs as export_jobs
from app.services import candidate_needs, downstream_metrics, sync_audit
from app.services import candidate_clusters
from app.services.export_jobs import ExportJobNotFoundError
from app.services.candidate_needs import (
    CandidateNeedNotFoundError,
    InvalidStatusTransitionError,
)
from app.services.raw_entries import RawEntryNotFoundError
from jobs import task_queue

router = APIRouter(prefix="/candidate-needs", tags=["Candidate Needs"])


@router.get("/", response_model=CandidateNeedList, summary="列出候选需求")
async def list_candidate_needs(
    skip: int = Query(default=0, ge=0, description="跳过的记录数量"),
    limit: int = Query(default=20, ge=1, le=200, description="返回的记录数量"),
    statuses: list[CandidateNeedStatusEnum] | None = Query(
        default=None,
        description="按状态过滤，可多选",
    ),
    search: str | None = Query(default=None, description="关键字搜索"),
    raw_entry_id: int | None = Query(default=None, description="关联的原始条目 ID"),
    source_type: SourceType | None = Query(default=None, description="按来源类型过滤"),
    candidate_type: CandidateNeedTypeEnum | None = Query(default=None, description="按候选类型过滤"),
    review_ready_only: bool | None = Query(default=None, description="仅显示默认评审队列"),
    min_review_readiness: float | None = Query(default=None, ge=0.0, le=1.0, description="最小评审就绪度"),
    synced: bool | None = Query(
        default=None,
        description="按同步状态过滤，true 表示已同步，false 表示未同步",
    ),
) -> CandidateNeedList:
    total, items = candidate_needs.list_needs(
        statuses=_convert_statuses(statuses),
        search=search,
        raw_entry_id=raw_entry_id,
        source_type=source_type,
        candidate_type=_convert_candidate_type(candidate_type),
        review_ready_only=review_ready_only,
        min_review_readiness=min_review_readiness,
        synced=synced,
        skip=skip,
        limit=limit,
    )
    return CandidateNeedList(
        total=total,
        items=_build_candidate_need_reads(items),
    )


@router.get(
    "/clusters",
    response_model=CandidateNeedClusterList,
    summary="聚合重复候选需求信号",
)
async def list_candidate_need_clusters(
    statuses: list[CandidateNeedStatusEnum] | None = Query(
        default=None,
        description="按状态过滤，可多选",
    ),
    search: str | None = Query(default=None, description="关键字搜索"),
    source_type: SourceType | None = Query(default=None, description="按来源类型过滤"),
    candidate_type: CandidateNeedTypeEnum | None = Query(default=None, description="按候选类型过滤"),
    review_ready_only: bool | None = Query(default=None, description="仅显示默认评审队列"),
    min_review_readiness: float | None = Query(default=None, ge=0.0, le=1.0, description="最小评审就绪度"),
    synced: bool | None = Query(default=None, description="按同步状态过滤"),
    limit: int = Query(default=100, ge=1, le=500, description="聚类时纳入计算的候选需求数量"),
    min_cluster_size: int = Query(default=2, ge=2, le=20, description="最小簇大小"),
    similarity_threshold: float = Query(
        default=0.25,
        ge=0.1,
        le=1.0,
        description="相似度阈值",
    ),
) -> CandidateNeedClusterList:
    normalized_statuses = _convert_statuses(statuses)
    clusters = candidate_clusters.summarize_clusters(
        statuses=tuple(normalized_statuses) if normalized_statuses is not None else None,
        search=search,
        source_type=source_type,
        candidate_type=_convert_candidate_type(candidate_type),
        review_ready_only=review_ready_only,
        min_review_readiness=min_review_readiness,
        synced=synced,
        limit=limit,
        min_cluster_size=min_cluster_size,
        similarity_threshold=similarity_threshold,
    )
    return CandidateNeedClusterList(
        total=len(clusters),
        items=[CandidateNeedClusterRead.model_validate(item) for item in clusters],
    )


@router.get(
    "/sync-logs",
    response_model=CandidateNeedSyncLogList,
    summary="最近候选需求同步日志",
)
async def list_recent_sync_logs(
    need_id: int | None = Query(default=None, description="按候选需求过滤"),
    channel: SyncChannelEnum | None = Query(default=None, description="按渠道过滤"),
    limit: int = Query(default=20, ge=1, le=200, description="返回的日志数量"),
) -> CandidateNeedSyncLogList:
    logs = sync_audit.list_logs(
        need_id=need_id,
        channel=_convert_sync_channel(channel),
        limit=limit,
    )
    return CandidateNeedSyncLogList(
        total=len(logs),
        items=[CandidateNeedSyncLogRead.model_validate(item) for item in logs],
    )


@router.get(
    "/sync-stats",
    response_model=list[CandidateNeedSyncChannelStat],
    summary="按渠道聚合的同步统计",
)
async def summarize_sync_channels(
    limit: int = Query(
        default=200,
        ge=10,
        le=1000,
        description="统计最近多少条审计日志",
    ),
) -> list[CandidateNeedSyncChannelStat]:
    stats = downstream_metrics.summarize_recent_sync_logs(limit=limit)
    return [
        CandidateNeedSyncChannelStat(
            channel=SyncChannelEnum(stat.channel.value),
            total_attempts=stat.total_attempts,
            success=stat.success,
            failed=stat.failed,
            pending=stat.pending,
            success_rate=round(stat.success_rate, 4),
            last_attempt_at=stat.last_attempt_at,
            last_error=stat.last_error,
        )
        for stat in stats
    ]


@router.post(
    "/",
    response_model=CandidateNeedRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建候选需求",
)
async def create_candidate_need(payload: CandidateNeedCreate) -> CandidateNeedRead:
    try:
        need = candidate_needs.create_need(
            {
                **payload.model_dump(exclude={"status"}),
                "status": _convert_status(payload.status),
            }
        )
    except RawEntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="关联的原始条目不存在",
        ) from exc
    return _build_candidate_need_reads([need])[0]


@router.get("/export", summary="导出候选需求")
async def export_candidate_needs(
    format: str = Query(default="json", pattern="^(json|csv)$", description="导出格式"),
    statuses: list[CandidateNeedStatusEnum] | None = Query(
        default=None,
        description="按状态过滤，可多选",
    ),
    search: str | None = Query(default=None, description="关键字搜索"),
    raw_entry_id: int | None = Query(default=None, description="关联的原始条目 ID"),
    source_type: SourceType | None = Query(default=None, description="按来源类型过滤"),
    candidate_type: CandidateNeedTypeEnum | None = Query(default=None, description="按候选类型过滤"),
    review_ready_only: bool | None = Query(default=None, description="仅显示默认评审队列"),
    min_review_readiness: float | None = Query(default=None, ge=0.0, le=1.0, description="最小评审就绪度"),
    synced: bool | None = Query(
        default=None,
        description="按同步状态过滤，true 表示已同步，false 表示未同步",
    ),
    limit: int | None = Query(default=None, ge=1, le=1000, description="最大导出数量"),
) -> dict:
    needs = candidate_needs.export_needs(
        statuses=_convert_statuses(statuses),
        search=search,
        raw_entry_id=raw_entry_id,
        source_type=source_type,
        candidate_type=_convert_candidate_type(candidate_type),
        review_ready_only=review_ready_only,
        min_review_readiness=min_review_readiness,
        synced=synced,
        limit=limit,
    )

    if format == "json":
        payload = [item.model_dump(mode="json") for item in _build_candidate_need_reads(needs)]
        return {"format": "json", "items": payload}

    buffer = StringIO()
    fieldnames = [
        "id",
        "raw_entry_id",
        "summary",
        "problem_statement",
        "target_users",
        "value_proposition",
        "competition",
        "candidate_type",
        "review_readiness",
        "confidence",
        "rule_score",
        "status",
        "notes",
        "created_at",
        "updated_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for model in _build_candidate_need_reads(needs):
        writer.writerow(
            {
                "id": model.id,
                "raw_entry_id": model.raw_entry_id,
                "summary": model.summary,
                "problem_statement": model.problem_statement or "",
                "target_users": model.target_users or "",
                "value_proposition": model.value_proposition or "",
                "competition": model.competition or "",
                "candidate_type": model.candidate_type.value if model.candidate_type else "",
                "review_readiness": model.review_readiness if model.review_readiness is not None else "",
                "confidence": model.confidence if model.confidence is not None else "",
                "rule_score": model.rule_score if model.rule_score is not None else "",
                "status": model.status.value,
                "notes": model.notes or "",
                "created_at": model.created_at.isoformat(),
                "updated_at": model.updated_at.isoformat(),
            }
        )
    return {"format": "csv", "content": buffer.getvalue()}


@router.get(
    "/export-tasks",
    response_model=CandidateNeedExportJobList,
    summary="导出任务列表",
)
async def list_candidate_need_export_tasks(
    status: ExportJobStatus | None = Query(
        default=None,
        description="按任务状态过滤",
    ),
    limit: int = Query(default=20, ge=1, le=200, description="最大返回数量"),
) -> CandidateNeedExportJobList:
    jobs = export_jobs.list_candidate_export_jobs(status=status, limit=limit)
    return CandidateNeedExportJobList(
        total=len(jobs),
        items=[CandidateNeedExportJobRead.model_validate(item) for item in jobs],
    )


@router.post(
    "/export-tasks",
    response_model=CandidateNeedExportJobRead,
    status_code=202,
    summary="创建候选需求导出任务",
)
async def create_candidate_need_export_task(
    payload: CandidateNeedExportJobCreate,
) -> CandidateNeedExportJobRead:
    job = export_jobs.create_candidate_export_job(
        format=payload.format,
        statuses=_convert_statuses(payload.statuses),
        search=payload.search,
        raw_entry_id=payload.raw_entry_id,
        source_type=payload.source_type,
        candidate_type=_convert_candidate_type(payload.candidate_type),
        review_ready_only=payload.review_ready_only,
        min_review_readiness=payload.min_review_readiness,
        synced=payload.synced,
        limit=payload.limit,
    )
    task_queue.enqueue_export_job(job.id)
    return CandidateNeedExportJobRead.model_validate(job)


@router.get(
    "/export-tasks/{job_id}",
    response_model=CandidateNeedExportJobRead,
    summary="导出任务详情",
)
async def get_candidate_need_export_task(job_id: int) -> CandidateNeedExportJobRead:
    try:
        job = export_jobs.get_export_job(job_id)
    except ExportJobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导出任务不存在") from exc
    return CandidateNeedExportJobRead.model_validate(job)


@router.get(
    "/{need_id}",
    response_model=CandidateNeedRead,
    summary="候选需求详情",
)
async def get_candidate_need(need_id: int) -> CandidateNeedRead:
    try:
        need = candidate_needs.get_need(need_id)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    return _build_candidate_need_reads([need])[0]


@router.put(
    "/{need_id}",
    response_model=CandidateNeedRead,
    summary="更新候选需求",
)
async def update_candidate_need(need_id: int, payload: CandidateNeedUpdate) -> CandidateNeedRead:
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        status_value = data["status"]
        if status_value is None:
            data.pop("status")
        else:
            data["status"] = _convert_status(status_value)
    try:
        need = candidate_needs.update_need(need_id, data)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    except RawEntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="关联的原始条目不存在",
        ) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _build_candidate_need_reads([need])[0]


@router.put(
    "/{need_id}/status",
    response_model=CandidateNeedRead,
    summary="更新候选需求状态",
)
async def update_candidate_need_status(
    need_id: int, payload: CandidateNeedStatusUpdate
) -> CandidateNeedRead:
    try:
        need = candidate_needs.update_need_status(need_id, _convert_status(payload.status))
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _build_candidate_need_reads([need])[0]


@router.delete(
    "/{need_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除候选需求",
)
async def delete_candidate_need(need_id: int) -> None:
    try:
        candidate_needs.delete_need(need_id)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc


@router.get(
    "/{need_id}/status-logs",
    response_model=list[CandidateNeedStatusLogRead],
    summary="候选需求状态流转日志",
)
async def list_candidate_need_status_logs(need_id: int) -> list[CandidateNeedStatusLogRead]:
    try:
        logs = candidate_needs.list_need_status_logs(need_id)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    return [CandidateNeedStatusLogRead.model_validate(item) for item in logs]


@router.get(
    "/{need_id}/sync-logs",
    response_model=list[CandidateNeedSyncLogRead],
    summary="候选需求下游同步日志",
)
async def list_candidate_need_sync_logs(
    need_id: int,
    limit: int = Query(default=50, ge=1, le=200, description="返回的日志数量"),
) -> list[CandidateNeedSyncLogRead]:
    try:
        candidate_needs.get_need(need_id)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    logs = sync_audit.list_logs(need_id=need_id, limit=limit)
    return [CandidateNeedSyncLogRead.model_validate(item) for item in logs]


def _convert_status(
    value: CandidateNeedStatusEnum | CandidateNeedStatus | str,
) -> CandidateNeedStatus:
    if isinstance(value, CandidateNeedStatus):
        return value
    if isinstance(value, CandidateNeedStatusEnum):
        raw = value.value
    else:
        raw = value
    return CandidateNeedStatus(raw)


def _convert_statuses(
    values: Iterable[CandidateNeedStatusEnum] | None,
) -> list[CandidateNeedStatus] | None:
    if values is None:
        return None
    return [_convert_status(value) for value in values]


def _convert_candidate_type(
    value: CandidateNeedTypeEnum | CandidateNeedType | None,
) -> CandidateNeedType | None:
    if value is None:
        return None
    if isinstance(value, CandidateNeedType):
        return value
    return CandidateNeedType(value.value)


def _convert_sync_channel(
    value: SyncChannelEnum | SyncChannel | None,
) -> SyncChannel | None:
    if value is None:
        return None
    if isinstance(value, SyncChannel):
        return value
    return SyncChannel(value.value)


def _build_candidate_need_reads(items: list[CandidateNeed]) -> list[CandidateNeedRead]:
    raw_entry_cache: dict[int, object | None] = {}
    source_cache: dict[int, RssSource | None] = {}
    payloads: list[CandidateNeedRead] = []
    for item in items:
        raw_entry = raw_entry_cache.get(item.raw_entry_id)
        if raw_entry is None:
            raw_entry = db.get_raw_entry(item.raw_entry_id)
            raw_entry_cache[item.raw_entry_id] = raw_entry
        source_name: str | None = None
        source_type: SourceType | None = None
        if raw_entry is not None:
            source = source_cache.get(raw_entry.source_id)
            if source is None:
                source = db.get_source(raw_entry.source_id)
                source_cache[raw_entry.source_id] = source
            if source is not None:
                source_name = source.name
                source_type = source.source_type
        review_signals = _build_review_signals(item, source_type)
        payloads.append(
            CandidateNeedRead.model_validate(
                {
                    **asdict(item),
                    "source_name": source_name,
                    "source_type": source_type,
                    "review_signals": review_signals,
                    "review_explanation": _build_review_explanation(
                        item,
                        source_type=source_type,
                        review_signals=review_signals,
                    ),
                }
            )
        )
    return payloads


def _build_review_signals(
    item: CandidateNeed,
    source_type: SourceType | None,
) -> list[str]:
    signals: list[str] = []
    if item.candidate_type is not None:
        signals.append(f"type:{item.candidate_type.value}")
    if source_type is not None:
        signals.append(f"source:{source_type.value}")
    if item.review_readiness is not None:
        if item.review_readiness >= 0.75:
            signals.append("review:high")
        elif item.review_readiness >= 0.55:
            signals.append("review:queue")
        else:
            signals.append("review:low")
    if item.rule_score is not None and item.rule_score >= 0.6:
        signals.append("rule:strong")
    elif item.rule_score is not None and item.rule_score >= 0.4:
        signals.append("rule:moderate")
    if item.confidence is not None and item.confidence >= 0.75:
        signals.append("confidence:high")
    elif item.confidence is not None and item.confidence >= 0.6:
        signals.append("confidence:medium")
    if item.problem_statement:
        signals.append("problem:present")
    if item.target_users:
        signals.append("user:present")
    return signals


def _build_review_explanation(
    item: CandidateNeed,
    *,
    source_type: SourceType | None,
    review_signals: list[str],
) -> str | None:
    readiness = item.review_readiness or 0.0
    if item.candidate_type == CandidateNeedType.WORKFLOW_PAIN:
        base = "这条候选被归为工作流痛点，说明它更像重复出现的流程摩擦，不只是一次性反馈。"
    elif item.candidate_type == CandidateNeedType.FEATURE_GAP:
        base = "这条候选被归为能力缺口，说明问题更接近稳定存在的产品缺失，而不是单点故障。"
    elif item.candidate_type == CandidateNeedType.TOOL_SEEKING:
        base = "这条候选被归为找工具/替代，说明它反映了明确的替代意图或选型需求。"
    elif item.candidate_type == CandidateNeedType.BUG_REPORT:
        base = "这条候选被归为故障反馈，默认不优先进入评审队列，除非它同时体现更广泛的能力缺口。"
    elif item.candidate_type == CandidateNeedType.MARKET_SIGNAL:
        base = "这条候选更偏市场信号，说明它有参考价值，但需求边界还不够清晰。"
    else:
        base = None

    details: list[str] = []
    if readiness >= 0.75:
        details.append("当前评审就绪度较高，适合直接进入人工评审。")
    elif readiness >= 0.55:
        details.append("当前评审就绪度达到默认队列阈值，可以进入待评审池。")
    else:
        details.append("当前评审就绪度偏低，更适合作为观察信号而不是立即评审。")
    if source_type == SourceType.GITHUB_ISSUES and item.candidate_type != CandidateNeedType.BUG_REPORT:
        details.append("虽然来源于 GitHub，但它已经被识别成比单纯 bug 更稳定的需求信号。")
    if "rule:strong" in review_signals:
        details.append("它命中了较强的筛选规则信号。")
    if "confidence:high" in review_signals:
        details.append("结构化提取的置信度也比较高。")
    if "problem:present" in review_signals and "user:present" in review_signals:
        details.append("问题陈述和目标用户都比较完整。")
    if base is None:
        return " ".join(details) or None
    return " ".join([base, *details])
