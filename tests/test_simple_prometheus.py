from __future__ import annotations

from app.core.simple_prometheus import (
    CollectorRegistry,
    Counter,
    Histogram,
    _format_labels,
    _resolve_labels,
    generate_latest,
)


def test_registry_register_and_collect() -> None:
    registry = CollectorRegistry()
    counter = Counter("test_total", "Test counter", registry=registry)
    collected = list(registry.collect())
    assert counter in collected


def test_registry_get_sample_value_returns_none_for_unknown() -> None:
    registry = CollectorRegistry()
    assert registry.get_sample_value("nonexistent") is None


def test_counter_inc_without_labels() -> None:
    c = Counter("requests_total", "Total requests")
    c.inc()
    c.inc(2)
    assert c.get_sample_value({}) == 3.0


def test_counter_inc_with_labels() -> None:
    c = Counter("http_total", "HTTP requests", labelnames=("method", "status"))
    c.labels(method="GET", status="200").inc()
    c.labels(method="GET", status="200").inc(2)
    c.labels(method="POST", status="201").inc()
    assert c.get_sample_value({"method": "GET", "status": "200"}) == 3.0
    assert c.get_sample_value({"method": "POST", "status": "201"}) == 1.0
    assert c.get_sample_value({"method": "DELETE"}) is None


def test_counter_render_empty() -> None:
    c = Counter("empty_total", "Empty counter")
    lines = c.render()
    assert any("empty_total 0" in line for line in lines)


def test_counter_render_with_values() -> None:
    c = Counter("hits_total", "Page hits", labelnames=("page",))
    c.labels(page="/home").inc(5)
    c.labels(page="/about").inc(3)
    lines = c.render()
    assert any("hits_total" in line and "5" in line for line in lines)


def test_histogram_observe() -> None:
    h = Histogram("latency_seconds", "Request latency", labelnames=(), buckets=(0.1, 0.5, 1.0))
    h.observe(0.05)
    h.observe(0.3)
    h.observe(2.0)
    h.observe(1.5)
    assert h.get_sample_value({}) == 4


def test_histogram_render() -> None:
    h = Histogram("dur_seconds", "Duration", labelnames=(), buckets=(0.5, 1.0))
    h.observe(0.3)
    lines = h.render()
    assert any("dur_seconds_bucket" in line for line in lines)
    assert any("dur_seconds_sum" in line for line in lines)
    assert any("dur_seconds_count" in line for line in lines)


def test_histogram_with_labels() -> None:
    h = Histogram("size_bytes", "Response size", labelnames=("endpoint",), buckets=(100, 1000))
    h.labels(endpoint="/api").observe(50)
    h.labels(endpoint="/api").observe(200)
    h.labels(endpoint="/health").observe(500)
    assert h.get_sample_value({"endpoint": "/api"}) == 2
    assert h.get_sample_value({"endpoint": "/health"}) == 1
    assert h.get_sample_value({"endpoint": "/none"}) is None


def test_counter_inc_with_positional_labels() -> None:
    c = Counter("pos_total", "Positional", labelnames=("a", "b"))
    c.labels("x", "y").inc()
    assert c.get_sample_value({"a": "x", "b": "y"}) == 1.0


def test_resolve_labels_with_dict() -> None:
    result = _resolve_labels(("name", "type"), (), {"name": "foo", "type": "bar"})
    assert result == ("foo", "bar")


def test_resolve_labels_with_positional() -> None:
    result = _resolve_labels(("name", "type"), ("foo", "bar"), {})
    assert result == ("foo", "bar")


def test_resolve_labels_mismatch_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="Label count mismatch"):
        _resolve_labels(("name",), ("too", "many"), {})


def test_resolve_labels_empty() -> None:
    result = _resolve_labels((), (), {})
    assert result == ()


def test_format_labels_empty() -> None:
    assert _format_labels([]) == ""
    assert _format_labels(()) == ""


def test_format_labels_with_values() -> None:
    result = _format_labels([("method", "GET"), ("status", "200")])
    assert 'method="GET"' in result
    assert 'status="200"' in result
    assert result.startswith("{")
    assert result.endswith("}")


def test_generate_latest() -> None:
    registry = CollectorRegistry()
    Counter("app_info", "Application info", registry=registry).inc(1)
    payload = generate_latest(registry)
    assert b"app_info" in payload
    assert b"HELP" in payload
    assert b"TYPE" in payload


def test_histogram_observe_direct() -> None:
    h = Histogram("direct_seconds", "Direct", labelnames=())
    h.observe(1.0)
    h.observe(5.0)
    assert h.get_sample_value({}) == 2


def test_registry_get_sample_value_with_labels() -> None:
    registry = CollectorRegistry()
    c = Counter("reg_total", "With registry", labelnames=("code",), registry=registry)
    c.labels(code="200").inc(3)
    assert registry.get_sample_value("reg_total", {"code": "200"}) == 3.0
    assert registry.get_sample_value("reg_total", {"code": "500"}) is None


def test_counter_render_includes_help_and_type() -> None:
    c = Counter("my_counter", "My counter help")
    rendered = c.render()
    assert "# HELP" in rendered[0]
    assert "# TYPE" in rendered[1]


def test_histogram_bucket_render_includes_inf() -> None:
    h = Histogram("buckets_hist", "Buckets test", labelnames=(), buckets=(0.5,))
    h.observe(0.3)
    lines = h.render()
    inf_lines = [line for line in lines if "+Inf" in line]
    assert len(inf_lines) > 0


def test_counter_get_sample_value_no_labels() -> None:
    c = Counter("nolabel_counter", "No labels", labelnames=())
    c.inc(10)
    assert c.get_sample_value({}) == 10.0
