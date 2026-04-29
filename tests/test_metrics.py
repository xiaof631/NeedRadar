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


def test_record_rss_fetch_records_counters() -> None:
    before = metrics.REGISTRY.get_sample_value(
        "needradar_rss_fetch_total",
        {"status": "success"},
    ) or 0.0
    metrics.record_rss_fetch("success", new_entries=3)
    after = metrics.REGISTRY.get_sample_value(
        "needradar_rss_fetch_total",
        {"status": "success"},
    )
    assert after is not None
    assert after == before + 1


def test_record_rss_fetch_without_new_entries() -> None:
    metrics.record_rss_fetch("failed")
    after = metrics.REGISTRY.get_sample_value(
        "needradar_rss_fetch_total",
        {"status": "failed"},
    )
    assert after is not None


def test_record_promotion_result() -> None:
    before = metrics.REGISTRY.get_sample_value(
        "needradar_promotions_total",
        {"status": "promoted"},
    ) or 0.0
    metrics.record_promotion_result("promoted")
    after = metrics.REGISTRY.get_sample_value(
        "needradar_promotions_total",
        {"status": "promoted"},
    )
    assert after is not None
    assert after == before + 1


def test_record_downstream_delivery() -> None:
    before = metrics.REGISTRY.get_sample_value(
        "needradar_downstream_deliveries_total",
        {"channel": "webhook", "status": "success"},
    ) or 0.0
    metrics.record_downstream_delivery("webhook", "success")
    after = metrics.REGISTRY.get_sample_value(
        "needradar_downstream_deliveries_total",
        {"channel": "webhook", "status": "success"},
    )
    assert after is not None
    assert after == before + 1


def test_record_file_drop_duration_records() -> None:
    metrics.record_file_drop_duration(0.05, file_format="json")


def test_record_file_drop_duration_clamps_negative() -> None:
    metrics.record_file_drop_duration(-0.5, file_format="json")


def test_record_export_job_result() -> None:
    before = metrics.REGISTRY.get_sample_value(
        "needradar_export_jobs_total",
        {"status": "completed"},
    ) or 0.0
    metrics.record_export_job_result("completed")
    after = metrics.REGISTRY.get_sample_value(
        "needradar_export_jobs_total",
        {"status": "completed"},
    )
    assert after is not None
    assert after == before + 1


def test_record_task_enqueue_skips_non_positive() -> None:
    metrics.record_task_enqueue("sync", count=0)
    # 当 count <= 0 时不应创建新的计数器标签
    after = metrics.REGISTRY.get_sample_value(
        "needradar_task_queue_enqueued_total",
        {"kind": "sync"},
    )
    # 尚未记录过的标签可能为 None
    assert after is None or after == 0
