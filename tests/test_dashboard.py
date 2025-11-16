from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.db.storage import db
from app.main import app
from app.models import CandidateNeedStatus, FetchStatus, RawEntryStatus, SourceStatus
from app.services import candidate_needs, dashboard, raw_entries, rss_sources
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


def _seed_dashboard_data() -> None:
    active_source = rss_sources.create_source(
        {
            "name": "Tech",
            "url": "https://example.com/tech.xml",
            "status": SourceStatus.ACTIVE,
            "frequency": 3600,
        }
    )
    paused_source = rss_sources.create_source(
        {
            "name": "News",
            "url": "https://example.com/news.xml",
            "status": SourceStatus.PAUSED,
            "frequency": 7200,
        }
    )

    base_time = datetime.now(UTC)
    pending_entry = raw_entries.create_entry(
        {
            "source_id": active_source.id,
            "guid": "pending",
            "title": "Pending entry",
            "published_at": base_time,
            "status": RawEntryStatus.PENDING,
        }
    )
    filtered_entry = raw_entries.create_entry(
        {
            "source_id": active_source.id,
            "guid": "filtered",
            "title": "Filtered entry",
            "published_at": base_time,
            "status": RawEntryStatus.FILTERED,
        }
    )
    promoted_entry = raw_entries.create_entry(
        {
            "source_id": paused_source.id,
            "guid": "promoted",
            "title": "Promoted entry",
            "published_at": base_time,
            "status": RawEntryStatus.PROMOTED,
        }
    )

    candidate_needs.create_need(
        {
            "raw_entry_id": filtered_entry.id,
            "summary": "Need pending",
            "status": CandidateNeedStatus.PENDING_REVIEW,
        }
    )
    synced_need = candidate_needs.create_need(
        {
            "raw_entry_id": promoted_entry.id,
            "summary": "Need approved",
            "status": CandidateNeedStatus.APPROVED,
        }
    )
    candidate_needs.mark_need_synced(synced_need.id)
    candidate_needs.create_need(
        {
            "raw_entry_id": pending_entry.id,
            "summary": "Need rejected",
            "status": CandidateNeedStatus.REJECTED,
        }
    )

    db.add_fetch_log(active_source.id, status=FetchStatus.SUCCESS, http_status=200)
    db.add_fetch_log(
        paused_source.id,
        status=FetchStatus.FAILURE,
        http_status=500,
        error_message="timeout",
    )


def test_dashboard_metrics_service() -> None:
    _seed_dashboard_data()

    metrics = dashboard.get_dashboard_metrics()

    assert metrics.sources.total == 2
    assert metrics.sources.active == 1
    assert metrics.raw_entries.total == 3
    assert metrics.raw_entries.by_status[RawEntryStatus.PENDING.value] == 1
    assert metrics.candidate_needs.total == 3
    assert metrics.candidate_needs.by_status[CandidateNeedStatus.APPROVED.value] == 1
    assert metrics.pending_sync_needs == 2
    assert metrics.fetch_logs.total == 2
    assert metrics.fetch_logs.failures == 1


def test_dashboard_metrics_api(client: TestClient) -> None:
    _seed_dashboard_data()

    response = client.get("/api/v1/dashboard/metrics")
    assert response.status_code == 200
    body = response.json()

    assert body["sources"]["total"] == 2
    assert body["sources"]["active"] == 1
    assert body["raw_entries"]["by_status"][RawEntryStatus.PENDING.value] == 1
    assert body["candidate_needs"]["by_status"][CandidateNeedStatus.REJECTED.value] == 1
    assert body["pending_sync_needs"] == 2
    assert body["fetch_logs"]["failures"] == 1
