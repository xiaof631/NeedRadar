from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.main import app
from app.models import RawEntryStatus, SourceStatus
from app.services import candidate_needs, filter_metrics, raw_entries, rss_sources
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _seed_filter_data() -> tuple[int, int]:
    source_a = rss_sources.create_source(
        {
            "name": "Tech Feed",
            "url": "https://example.com/tech.xml",
            "status": SourceStatus.ACTIVE,
            "frequency": 3600,
        }
    )
    source_b = rss_sources.create_source(
        {
            "name": "News Feed",
            "url": "https://example.com/news.xml",
            "status": SourceStatus.PAUSED,
            "frequency": 7200,
        }
    )
    now = datetime.now(UTC)
    pending_entry = raw_entries.create_entry(
        {
            "source_id": source_a.id,
            "guid": "pending",
            "title": "Pending entry",
            "published_at": now,
            "status": RawEntryStatus.PENDING,
        }
    )
    raw_entries.create_entry(
        {
            "source_id": source_a.id,
            "guid": "filtered",
            "title": "Filtered entry",
            "published_at": now,
            "status": RawEntryStatus.FILTERED,
        }
    )
    promoted_a = raw_entries.create_entry(
        {
            "source_id": source_a.id,
            "guid": "promoted-a",
            "title": "Promoted entry A",
            "published_at": now,
            "status": RawEntryStatus.PROMOTED,
        }
    )
    promoted_b = raw_entries.create_entry(
        {
            "source_id": source_b.id,
            "guid": "promoted-b",
            "title": "Promoted entry B",
            "published_at": now,
            "status": RawEntryStatus.PROMOTED,
        }
    )
    raw_entries.create_entry(
        {
            "source_id": source_b.id,
            "guid": "ignored",
            "title": "Ignored entry",
            "published_at": now,
            "status": RawEntryStatus.IGNORED,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": promoted_a.id,
            "summary": "Need A",
            "rule_score": 0.8,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": promoted_b.id,
            "summary": "Need B",
            "rule_score": 0.6,
        }
    )
    return source_a.id, pending_entry.id


def test_filter_metrics_service() -> None:
    source_a_id, _ = _seed_filter_data()

    metrics = filter_metrics.get_filter_performance()

    assert metrics.total_entries == 5
    assert metrics.pending_entries == 1
    assert metrics.processed_entries == 4
    assert metrics.filtered_entries == 1
    assert metrics.promoted_entries == 2
    assert metrics.ignored_entries == 1
    assert metrics.promotion_rate == 0.5
    assert metrics.average_rule_score == 0.7

    breakdown = {item.source_id: item for item in metrics.source_breakdown}
    assert breakdown[source_a_id].promotion_rate == 0.5
    assert breakdown[source_a_id].filtered_entries == 1


def test_filter_metrics_api(client: TestClient) -> None:
    source_a_id, _ = _seed_filter_data()

    response = client.get("/api/v1/filter-metrics")
    assert response.status_code == 200
    body = response.json()

    assert body["total_entries"] == 5
    assert body["pending_entries"] == 1
    assert body["promotion_rate"] == 0.5
    assert body["average_rule_score"] == 0.7

    breakdown = body["source_breakdown"]
    assert len(breakdown) == 2
    first = next(item for item in breakdown if item["source_id"] == source_a_id)
    assert first["promoted_entries"] == 1
    assert first["pending_entries"] == 1
