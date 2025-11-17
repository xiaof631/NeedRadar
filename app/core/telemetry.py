"""OpenTelemetry 集成与工具方法。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.core.config import get_settings
from fastapi import FastAPI

try:  # pragma: no cover - OpenTelemetry 为可选依赖
    from opentelemetry import trace as ot_trace  # type: ignore
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import (  # type: ignore
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SpanExporter,
    )
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased  # type: ignore
except ImportError:  # pragma: no cover
    ot_trace = None
    FastAPIInstrumentor = None
    OTLPSpanExporter = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None
    SpanExporter = None
    TraceIdRatioBased = None


_instrumented = False


def instrument_app(app: FastAPI) -> None:
    """根据配置为 FastAPI 应用注入 OpenTelemetry。"""

    global _instrumented
    settings = get_settings()
    if not settings.telemetry_enabled or _instrumented or _otel_missing():
        return

    resource = Resource.create({"service.name": settings.telemetry_service_name})  # type: ignore[arg-type]
    provider = TracerProvider(  # type: ignore[call-arg]
        resource=resource,
        sampler=TraceIdRatioBased(settings.telemetry_sample_ratio),
    )
    exporter = _build_exporter(
        endpoint=settings.telemetry_otlp_endpoint,
        insecure=settings.telemetry_otlp_insecure,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))  # type: ignore[call-arg]
    ot_trace.set_tracer_provider(provider)  # type: ignore[union-attr]

    excluded = ",".join(settings.telemetry_excluded_urls)
    FastAPIInstrumentor.instrument_app(  # type: ignore[call-arg]
        app,
        tracer_provider=provider,
        excluded_urls=excluded,
    )
    _instrumented = True


def get_tracer(name: str) -> Any:
    """返回统一的 tracer，若未安装 OpenTelemetry 则回退为 no-op。"""

    if ot_trace is None:
        return _NoopTracer()
    return ot_trace.get_tracer(name)


def _build_exporter(*, endpoint: str | None, insecure: bool) -> Any:
    if endpoint and OTLPSpanExporter is not None:
        return OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    return ConsoleSpanExporter()  # type: ignore[call-arg]


def _otel_missing() -> bool:
    return any(
        dependency is None
        for dependency in (
            ot_trace,
            FastAPIInstrumentor,
            Resource,
            TracerProvider,
            BatchSpanProcessor,
            ConsoleSpanExporter,
            TraceIdRatioBased,
        )
    )


class _NoopTracer:
    def start_as_current_span(self, _: str):
        return _noop_span()


@contextmanager
def _noop_span():
    yield None


__all__ = ["instrument_app", "get_tracer"]
