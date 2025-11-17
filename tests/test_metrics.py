from app.core import metrics
from app.main import app
from fastapi.testclient import TestClient


def test_metrics_endpoint_exposes_http_counters() -> None:
    client = TestClient(app)
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "needradar_http_requests_total" in response.text


def test_record_helpers_update_registry() -> None:
    before = metrics.REGISTRY.get_sample_value(
        "needradar_task_queue_enqueued_total",
        {"kind": "fetch"},
    ) or 0.0
    metrics.record_task_enqueue("fetch", count=2)
    after = metrics.REGISTRY.get_sample_value(
        "needradar_task_queue_enqueued_total",
        {"kind": "fetch"},
    )
    assert after is not None
    assert after == before + 2
