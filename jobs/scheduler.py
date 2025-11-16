"""APScheduler 驱动的调度入口。"""

from __future__ import annotations

import asyncio
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from jobs import tasks

logger = get_logger(__name__)


async def _run_fetch_job() -> None:
    """抓取所有启用的数据源并记录摘要信息。"""

    try:
        results = await tasks.fetch_active_sources()
    except Exception:  # pragma: no cover - 调度器异常记录
        logger.exception("scheduler.fetch.failed")
        return

    fetched = sum(result.fetched_entries for result in results)
    inserted = sum(result.new_entries for result in results)
    logger.info(
        "scheduler.fetch.completed",
        sources=len(results),
        fetched_entries=fetched,
        new_entries=inserted,
    )


def _run_promote_job(
    *,
    batch_size: int,
    min_score: float | None,
) -> None:
    """运行候选需求晋升任务并记录统计。"""

    try:
        results = tasks.promote_pending_entries(
            batch_size=batch_size,
            min_score=min_score,
        )
    except Exception:  # pragma: no cover - 调度器异常记录
        logger.exception("scheduler.promote.failed")
        return

    logger.info("scheduler.promote.completed", promoted=len(results))


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
    scheduler.start()
    logger.info(
        "scheduler.started",
        fetch_interval=settings.scheduler_fetch_interval_seconds,
        promote_interval=settings.scheduler_promote_interval_seconds,
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
