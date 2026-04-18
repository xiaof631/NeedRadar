"""Prometheus 指标与中间件。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

try:  # pragma: no cover - 依赖在本地环境可能不可用
    from prometheus_client import (  # type: ignore
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest,
    )
except ImportError:  # pragma: no cover - fallback 实现
    from app.core.simple_prometheus import (  # type: ignore
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest,
    )
from fastapi import APIRouter, Response

REGISTRY = CollectorRegistry()

_http_requests_total = Counter(
    "needradar_http_requests_total",
    "HTTP 请求数量（按方法/路径/状态码拆分）",
    ("method", "path", "status_code"),
    registry=REGISTRY,
)
_http_request_duration = Histogram(
    "needradar_http_request_duration_seconds",
    "HTTP 请求耗时（秒）",
    ("method", "path"),
    registry=REGISTRY,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
_rss_fetch_total = Counter(
    "needradar_rss_fetch_total",
    "RSS 抓取任务数量（按结果拆分）",
    ("status",),
    registry=REGISTRY,
)
_rss_entries_ingested = Counter(
    "needradar_rss_entries_ingested_total",
    "抓取后写入的新条目数量",
    registry=REGISTRY,
)
_promotion_total = Counter(
    "needradar_promotions_total",
    "候选需求晋升结果数量",
    ("status",),
    registry=REGISTRY,
)
_downstream_total = Counter(
    "needradar_downstream_deliveries_total",
    "下游同步结果数量",
    ("channel", "status"),
    registry=REGISTRY,
)
_file_drop_duration = Histogram(
    "needradar_downstream_file_drop_duration_seconds",
    "file drop 通道落盘耗时（秒）",
    ("format",),
    registry=REGISTRY,
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0),
)
_export_jobs_total = Counter(
    "needradar_export_jobs_total",
    "导出任务执行结果数量",
    ("status",),
    registry=REGISTRY,
)
_task_queue_enqueued = Counter(
    "needradar_task_queue_enqueued_total",
    "入队任务数量（按类型拆分）",
    ("kind",),
    registry=REGISTRY,
)


metrics_router = APIRouter()


@metrics_router.get("/metrics")
async def metrics_endpoint() -> Response:
    """导出 Prometheus 指标。"""

    payload = generate_latest(REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


def record_rss_fetch(status: str, *, new_entries: int = 0) -> None:
    """记录单次 RSS 抓取的结果。"""

    _rss_fetch_total.labels(status=status).inc()
    if new_entries > 0:
        _rss_entries_ingested.inc(new_entries)


def record_promotion_result(status: str) -> None:
    """记录候选需求晋升结果。"""

    _promotion_total.labels(status=status).inc()


def record_downstream_delivery(channel: str, status: str) -> None:
    """记录下游同步结果。"""

    _downstream_total.labels(channel=channel, status=status).inc()


def record_file_drop_duration(duration: float, *, file_format: str) -> None:
    """记录 file drop 通道一次写入的耗时。"""

    if duration < 0:
        duration = 0
    _file_drop_duration.labels(format=file_format).observe(duration)


def record_export_job_result(status: str) -> None:
    """记录导出任务执行状态。"""

    _export_jobs_total.labels(status=status).inc()


def record_task_enqueue(kind: str, *, count: int) -> None:
    """记录一次入队操作。"""

    if count <= 0:
        return
    _task_queue_enqueued.labels(kind=kind).inc(count)


def instrument_fastapi_app(app: Any) -> None:
    """为真实 FastAPI 或简化兼容层注入请求级指标。"""

    if getattr(app, "_needradar_metrics_instrumented", False):
        return

    if hasattr(app, "middleware"):
        @app.middleware("http")
        async def instrumented_http_requests(request: Any, call_next: Callable[..., Awaitable[Any]]) -> Any:
            start = perf_counter()
            status_code = "500"
            try:
                response = await call_next(request)
                status_code = str(getattr(response, "status_code", 200))
                return response
            finally:
                duration = perf_counter() - start
                _http_requests_total.labels(
                    method=request.method.upper(),
                    path=request.url.path,
                    status_code=status_code,
                ).inc()
                _http_request_duration.labels(
                    method=request.method.upper(),
                    path=request.url.path,
                ).observe(duration)

        app._needradar_metrics_instrumented = True  # type: ignore[attr-defined]
        return

    original_dispatch: Callable[..., Awaitable[tuple[int, Any]]] = app.dispatch

    async def instrumented_dispatch(
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        start = perf_counter()
        status_code = "500"
        try:
            status, payload = await original_dispatch(
                method,
                path,
                params=params,
                json=json,
                headers=headers,
            )
            status_code = str(status)
            return status, payload
        finally:
            duration = perf_counter() - start
            normalized_method = method.upper()
            _http_requests_total.labels(
                method=normalized_method,
                path=path,
                status_code=status_code,
            ).inc()
            _http_request_duration.labels(method=normalized_method, path=path).observe(duration)

    app.dispatch = instrumented_dispatch  # type: ignore[assignment]
    app._needradar_metrics_instrumented = True  # type: ignore[attr-defined]


__all__ = [
    "metrics_router",
    "instrument_fastapi_app",
    "record_rss_fetch",
    "record_promotion_result",
    "record_downstream_delivery",
    "record_file_drop_duration",
    "record_export_job_result",
    "record_task_enqueue",
    "REGISTRY",
]
