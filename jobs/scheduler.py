# ruff: noqa: E402

"""APScheduler 驱动的调度入口。"""

from __future__ import annotations

import asyncio
import signal

from runtime_bootstrap import prefer_installed_packages

prefer_installed_packages()

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models import CandidateNeedStatus
from jobs import task_queue

logger = get_logger(__name__)


async def _run_fetch_job() -> None:
    """抓取所有启用的数据源并记录摘要信息。"""

    try:
        queued = task_queue.enqueue_fetch_sources()
    except Exception as exc:  # pragma: no cover - 调度器异常记录
        logger.error("scheduler.fetch.failed", error=str(exc))
        return

    logger.info(
        "scheduler.fetch.completed",
        queued=queued,
    )


def _run_promote_job(
    *,
    batch_size: int,
    min_score: float | None,
) -> None:
    """运行候选需求晋升任务并记录统计。"""

    try:
        queued = task_queue.enqueue_promotions(
            batch_size=batch_size,
            min_score=min_score,
        )
    except Exception as exc:  # pragma: no cover - 调度器异常记录
        logger.error("scheduler.promote.failed", error=str(exc))
        return

    logger.info("scheduler.promote.completed", queued=queued)


def _run_stale_archive_job(*, stale_after_days: int) -> None:
    """派发陈旧线索归档任务。"""

    try:
        task_queue.archive_stale_leads_task.delay(stale_after_days)
    except Exception as exc:  # pragma: no cover - 调度器异常记录
        logger.error("scheduler.archive_stale.failed", error=str(exc))
        return
    logger.info("scheduler.archive_stale.queued", stale_after_days=stale_after_days)


def _run_keyword_extract_job() -> None:
    """派发关键词种子抽取任务。"""

    try:
        task_queue.extract_keyword_seeds_task.delay()
    except Exception as exc:  # pragma: no cover - 调度器异常记录
        logger.error("scheduler.keyword_extract.failed", error=str(exc))
        return
    logger.info("scheduler.keyword_extract.queued")


def _run_keyword_validate_job(*, batch_size: int) -> None:
    """派发关键词搜索量验证任务。"""

    try:
        task_queue.validate_keyword_seeds_task.delay(batch_size)
    except Exception as exc:  # pragma: no cover - 调度器异常记录
        logger.error("scheduler.keyword_validate.failed", error=str(exc))
        return
    logger.info("scheduler.keyword_validate.queued", batch_size=batch_size)


async def _run_sync_job(
    *,
    webhook_url: str | None,
    statuses: tuple[CandidateNeedStatus, ...],
    batch_size: int,
) -> None:
    """调度候选需求同步任务。"""

    try:
        queued = task_queue.enqueue_sync_tasks(
            webhook_url=webhook_url,
            statuses=statuses,
            batch_size=batch_size,
        )
    except Exception as exc:  # pragma: no cover - 调度器异常记录
        logger.error("scheduler.sync.failed", error=str(exc))
        return

    logger.info("scheduler.sync.completed", queued=queued)


async def main() -> None:
    """启动调度器直至收到终止信号。"""

    configure_logging()
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_fetch_job,
        trigger=IntervalTrigger(seconds=settings.scheduler_fetch_interval_seconds),
        id="fetch-rss",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_promote_job,
        trigger=IntervalTrigger(seconds=settings.scheduler_promote_interval_seconds),
        id="promote-entries",
        kwargs={
            "batch_size": settings.scheduler_promotion_batch_size,
            "min_score": settings.scheduler_min_rule_score,
        },
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_stale_archive_job,
        trigger=IntervalTrigger(
            seconds=settings.scheduler_stale_archive_interval_seconds
        ),
        id="archive-stale-leads",
        kwargs={"stale_after_days": settings.stale_lead_after_days},
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_keyword_extract_job,
        trigger=IntervalTrigger(
            seconds=settings.scheduler_keyword_extract_interval_seconds
        ),
        id="extract-keyword-seeds",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_keyword_validate_job,
        trigger=IntervalTrigger(
            seconds=settings.scheduler_keyword_validate_interval_seconds
        ),
        id="validate-keyword-seeds",
        kwargs={"batch_size": settings.keyword_validation_batch_size},
        max_instances=1,
        coalesce=True,
    )
    if (
        settings.downstream_webhook_url
        or settings.downstream_mq_enabled
        or settings.downstream_filesystem_enabled
    ):
        scheduler.add_job(
            _run_sync_job,
            trigger=IntervalTrigger(seconds=settings.scheduler_downstream_interval_seconds),
            id="sync-downstream",
            kwargs={
                "webhook_url": settings.downstream_webhook_url,
                "statuses": settings.downstream_sync_statuses,
                "batch_size": settings.downstream_sync_batch_size,
            },
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
    logger.info(
        "scheduler.started",
        fetch_interval=settings.scheduler_fetch_interval_seconds,
        promote_interval=settings.scheduler_promote_interval_seconds,
        stale_archive_interval=settings.scheduler_stale_archive_interval_seconds,
        stale_after_days=settings.stale_lead_after_days,
        keyword_extract_interval=settings.scheduler_keyword_extract_interval_seconds,
        keyword_validate_interval=settings.scheduler_keyword_validate_interval_seconds,
        downstream_interval=settings.scheduler_downstream_interval_seconds
        if (
            settings.downstream_webhook_url
            or settings.downstream_mq_enabled
            or settings.downstream_filesystem_enabled
        )
        else None,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signame in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signame, stop_event.set)
        except NotImplementedError:  # pragma: no cover - 平台不支持 signal
            signal.signal(signame, lambda *_: stop_event.set())

    await stop_event.wait()
    scheduler.shutdown()
    logger.info("scheduler.stopped")


if __name__ == "__main__":  # pragma: no cover - 手动运行入口
    asyncio.run(main())
