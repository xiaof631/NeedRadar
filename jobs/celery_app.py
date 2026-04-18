# ruff: noqa: E402

"""Celery 应用实例定义。"""

from __future__ import annotations

from datetime import timedelta

from runtime_bootstrap import prefer_installed_packages

prefer_installed_packages()

try:  # pragma: no cover - 真实环境会安装 celery
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - 离线测试兜底
    from jobs.simple_celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("needradar")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_default_queue=settings.celery_task_default_queue,
    task_always_eager=settings.celery_task_always_eager,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    enable_utc=True,
    timezone="UTC",
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,
)

# 自动发现 jobs.tasks 及 jobs.task_queue 模块中的任务定义。
celery_app.autodiscover_tasks(["jobs"])
celery_app.autodiscover_tasks(["jobs"], related_name="task_queue")

# 基于配置生成默认的 Beat 调度（可通过 Celery beat 或 APScheduler 调用）。
celery_app.conf.beat_schedule = {
    "enqueue-fetch-sources": {
        "task": "jobs.task_queue.enqueue_fetch_sources_task",
        "schedule": timedelta(seconds=settings.scheduler_fetch_interval_seconds),
    },
    "enqueue-promotions": {
        "task": "jobs.task_queue.enqueue_promotions_task",
        "schedule": timedelta(seconds=settings.scheduler_promote_interval_seconds),
        "args": [settings.scheduler_promotion_batch_size, settings.scheduler_min_rule_score],
    },
}

if settings.downstream_webhook_url:
    celery_app.conf.beat_schedule["enqueue-sync-downstream"] = {
        "task": "jobs.task_queue.enqueue_sync_task",
        "schedule": timedelta(seconds=settings.scheduler_downstream_interval_seconds),
        "args": [
            settings.downstream_webhook_url,
            [status.value for status in settings.downstream_sync_statuses],
            settings.downstream_sync_batch_size,
        ],
    }

__all__ = ["celery_app"]
