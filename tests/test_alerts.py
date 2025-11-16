from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.storage import db
from app.main import app
from app.models import CandidateNeedStatus, FetchStatus, RawEntryStatus, SourceStatus
from app.services import alerts, candidate_needs, raw_entries, rss_sources
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


def _seed_source(status: SourceStatus = SourceStatus.ACTIVE) -> int:
    source = rss_sources.create_source(
        {
            "name": "Tech",
            "url": f"https://example.com/{status.value}.xml",
            "status": status,
            "frequency": 3600,
        }
    )
    return source.id


def test_alert_for_missing_active_sources() -> None:
    generated = alerts.generate_system_alerts()

    assert any(alert.code == "no_active_sources" for alert in generated)


def test_alert_for_fetch_failures() -> None:
    source_id = _seed_source()
    db.add_fetch_log(source_id, status=FetchStatus.FAILURE, http_status=500)
    db.add_fetch_log(source_id, status=FetchStatus.FAILURE, http_status=500)
    db.add_fetch_log(source_id, status=FetchStatus.SUCCESS, http_status=200)

    generated = alerts.generate_system_alerts(fetch_failure_ratio_threshold=0.5)

    failure_alerts = [alert for alert in generated if alert.code == "fetch_failure_ratio_high"]
    assert failure_alerts
    assert failure_alerts[0].severity.value in {"warning", "critical"}


def test_alert_for_pending_entries_backlog() -> None:
    source_id = _seed_source()
    for index in range(5):
        raw_entries.create_entry(
            {
                "source_id": source_id,
                "guid": f"pending-{index}",
                "title": f"Entry {index}",
                "status": RawEntryStatus.PENDING,
                "published_at": datetime.now(UTC),
            }
        )

    generated = alerts.generate_system_alerts(pending_entries_threshold=3)

    backlog_alerts = [alert for alert in generated if alert.code == "pending_entries_backlog"]
    assert backlog_alerts
    assert backlog_alerts[0].details["pending_entries"] == 5


def test_alert_for_unsynced_candidate_needs() -> None:
    source_id = _seed_source()
    entry = raw_entries.create_entry(
        {
            "source_id": source_id,
            "guid": "seed",
            "title": "Need entry",
            "status": RawEntryStatus.PROMOTED,
            "published_at": datetime.now(UTC),
        }
    )
    for idx in range(3):
        candidate_needs.create_need(
            {
                "raw_entry_id": entry.id,
                "summary": f"Need {idx}",
                "status": CandidateNeedStatus.PENDING_REVIEW,
            }
        )

    generated = alerts.generate_system_alerts(
        unsynced_needs_threshold=2,
        pending_entries_threshold=10,
    )

    unsynced_alerts = [alert for alert in generated if alert.code == "unsynced_candidate_needs"]
    assert unsynced_alerts
    assert unsynced_alerts[0].details["unsynced"] == 3


def test_alert_for_stale_sources() -> None:
    source_id = _seed_source()
    rss_sources.update_source(
        source_id,
        {"last_fetched_at": datetime.now(UTC) - timedelta(hours=5)},
    )

    generated = alerts.generate_system_alerts(stale_source_threshold_minutes=60)

    stale_alerts = [alert for alert in generated if alert.code == "rss_sources_stale"]
    assert stale_alerts
    payload = stale_alerts[0].details
    assert payload["threshold_minutes"] == 60
    assert payload["stale_sources"][0]["source_id"] == source_id


def test_stale_sources_alert_critical_when_never_fetched() -> None:
    _seed_source()

    generated = alerts.generate_system_alerts(stale_source_threshold_minutes=60)

    stale_alerts = [alert for alert in generated if alert.code == "rss_sources_stale"]
    assert stale_alerts
    assert stale_alerts[0].severity == alerts.AlertSeverity.CRITICAL


def test_dashboard_alerts_api(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard/alerts")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["code"] == "no_active_sources"
