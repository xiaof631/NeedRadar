"""任务队列与 Celery task 定义。"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import httpx

from app.core import metrics
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.telemetry import get_tracer
from app.models import CandidateNeedStatus, RawEntryStatus, SourceStatus
from app.services import (
    candidate_needs,
    downstream,
    pipeline,
    raw_entries,
    rss_fetcher,
    rss_sources,
)
from app.services.pipeline import CandidateAlreadyExistsError, EntryNotQualifiedError
from jobs.celery_app import celery_app

logger: Any = get_logger(__name__)
settings = get_settings()
tracer = get_tracer(__name__)


@celery_app.task(
    name="jobs.fetch_rss_source",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def fetch_rss_source_task(self, source_id: int) -> dict[str, Any]:
    """抓取单个 RSS 源。"""

    logger.info("tasks.fetch_source.queued", source_id=source_id, task_id=self.request.id)
    with tracer.start_as_current_span("fetch_rss_source_task"):
        result = asyncio.run(rss_fetcher.fetch_rss_source(source_id))
    logger.info(
        "tasks.fetch_source.completed",
        source_id=source_id,
        fetched=result.fetched_entries,
        inserted=result.new_entries,
    )
    return {
        "source_id": result.source_id,
        "fetched_entries": result.fetched_entries,
        "new_entries": result.new_entries,
        "status": result.status.value,
        "error_message": result.error_message,
    }


@celery_app.task(name="jobs.promote_entry", bind=True)
def promote_entry_task(self, entry_id: int, min_score: float | None = None) -> dict[str, Any]:
    """将单条原始内容晋升为候选需求。"""

    logger.info("tasks.promote.queued", entry_id=entry_id, task_id=self.request.id)
    try:
        with tracer.start_as_current_span("promote_entry_task"):
            result = pipeline.promote_entry(entry_id, min_score=min_score)
    except EntryNotQualifiedError:
        logger.info("tasks.promote.skipped", entry_id=entry_id, reason="not-qualified")
        metrics.record_promotion_result("not-qualified")
        return {"entry_id": entry_id, "status": "skipped", "reason": "not-qualified"}
    except CandidateAlreadyExistsError as exc:
        logger.info(
            "tasks.promote.skipped",
            entry_id=entry_id,
            reason="duplicate",
            need_id=exc.need_id,
        )
        metrics.record_promotion_result("duplicate")
        return {
            "entry_id": entry_id,
            "status": "skipped",
            "reason": "duplicate",
            "candidate_need_id": exc.need_id,
        }

    logger.info(
        "tasks.promote.completed",
        entry_id=entry_id,
        candidate_need_id=result.candidate_need.id,
        rule_score=result.rule_match.score,
    )
    return {
        "entry_id": entry_id,
        "status": "promoted",
        "candidate_need_id": result.candidate_need.id,
        "rule_score": result.rule_match.score,
    }


async def _sync_candidate_need(need_id: int, webhook_url: str) -> dict[str, Any]:
    need = candidate_needs.get_need(need_id)
    async with httpx.AsyncClient(
        timeout=settings.celery_downstream_request_timeout,
    ) as client:
        result = await downstream.deliver_need_to_webhook(
            need,
            webhook_url=webhook_url,
            client=client,
        )
    return {
        "need_id": result.need_id,
        "success": result.success,
        "status_code": result.status_code,
        "error": result.error,
    }


@celery_app.task(
    name="jobs.sync_candidate_need",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 5},
)
def sync_candidate_need_task(self, need_id: int, webhook_url: str) -> dict[str, Any]:
    """推送单条候选需求至 Webhook。"""

    logger.info("tasks.sync.queued", need_id=need_id, task_id=self.request.id)
    with tracer.start_as_current_span("sync_candidate_need_task"):
        result = asyncio.run(_sync_candidate_need(need_id, webhook_url))
    logger.info("tasks.sync.completed", need_id=need_id, success=result["success"])
    return result


def enqueue_fetch_sources(*, limit: int | None = None) -> int:
    """扫描启用的数据源并为每个数据源派发 Celery 任务。"""

    _, sources = rss_sources.list_sources(status=SourceStatus.ACTIVE, limit=limit)
    for source in sources:
        fetch_rss_source_task.delay(source.id)
    count = len(sources)
    metrics.record_task_enqueue("fetch", count=count)
    return count


def enqueue_promotions(*, batch_size: int | None = None, min_score: float | None = None) -> int:
    """选取待处理的原始条目并派发晋升任务。"""

    limit = batch_size or settings.scheduler_promotion_batch_size
    _, entries = raw_entries.list_entries(status=RawEntryStatus.PENDING, limit=limit)
    for entry in entries:
        promote_entry_task.delay(entry.id, min_score)
    count = len(entries)
    metrics.record_task_enqueue("promote", count=count)
    return count


def enqueue_sync_tasks(
    *,
    webhook_url: str | None = None,
    statuses: Sequence[CandidateNeedStatus | str] | None = None,
    batch_size: int | None = None,
) -> int:
    """派发待同步候选需求的 Webhook 推送任务。"""

    target_url = webhook_url or settings.downstream_webhook_url
    if not target_url:
        return 0
    normalized_statuses = _normalize_statuses(statuses)
    limit = batch_size or settings.downstream_sync_batch_size
    needs = candidate_needs.list_unsynced_needs(statuses=normalized_statuses, limit=limit)
    for need in needs:
        sync_candidate_need_task.delay(need.id, target_url)
    count = len(needs)
    metrics.record_task_enqueue("sync", count=count)
    return count


def _normalize_statuses(
    statuses: Sequence[CandidateNeedStatus | str] | None,
) -> Sequence[CandidateNeedStatus] | None:
    if statuses is None:
        return settings.downstream_sync_statuses
    normalized: list[CandidateNeedStatus] = []
    for status in statuses:
        if isinstance(status, CandidateNeedStatus):
            normalized.append(status)
        else:
            normalized.append(CandidateNeedStatus(status))
    return tuple(normalized)


@celery_app.task(name="jobs.task_queue.enqueue_fetch_sources_task")
def enqueue_fetch_sources_task(limit: int | None = None) -> dict[str, Any]:
    queued = enqueue_fetch_sources(limit=limit)
    logger.info("tasks.enqueue.fetch", queued=queued)
    return {"queued": queued}


@celery_app.task(name="jobs.task_queue.enqueue_promotions_task")
def enqueue_promotions_task(batch_size: int, min_score: float | None) -> dict[str, Any]:
    queued = enqueue_promotions(batch_size=batch_size, min_score=min_score)
    logger.info("tasks.enqueue.promote", queued=queued)
    return {"queued": queued}


@celery_app.task(name="jobs.task_queue.enqueue_sync_task")
def enqueue_sync_task(
    webhook_url: str | None = None,
    statuses: Sequence[CandidateNeedStatus | str] | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    queued = enqueue_sync_tasks(webhook_url=webhook_url, statuses=statuses, batch_size=batch_size)
    logger.info("tasks.enqueue.sync", queued=queued)
    return {"queued": queued}


__all__ = [
    "enqueue_fetch_sources",
    "enqueue_promotions",
    "enqueue_sync_tasks",
    "fetch_rss_source_task",
    "promote_entry_task",
    "sync_candidate_need_task",
]
