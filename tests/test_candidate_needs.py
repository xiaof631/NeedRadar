from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.main import app
from app.models import CandidateNeedStatus, RawEntryStatus, SourceStatus
from app.services import candidate_needs, raw_entries, rss_sources
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


def _seed_candidate_needs() -> tuple[int, list[int]]:
    source = rss_sources.create_source(
        {
            "name": "Tech",
            "url": "https://example.com/tech.xml",
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-1",
            "title": "AI Ideas",
            "summary": "AI powered analytics",
            "published_at": datetime.now(UTC),
            "status": RawEntryStatus.PROMOTED,
        }
    )
    other_entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-2",
            "title": "Product Ops",
            "summary": "Collaboration tooling",
            "published_at": datetime.now(UTC),
            "status": RawEntryStatus.FILTERED,
        }
    )
    needs = [
        candidate_needs.create_need(
            {
                "raw_entry_id": entry.id,
                "summary": "Analytics assistant",
                "problem_statement": "Hard to monitor usage trends",
                "target_users": "Product managers",
                "value_proposition": "自动化分析关键信号",
                "competition": "Spreadsheet",
                "confidence": 0.7,
                "rule_score": 0.82,
                "status": CandidateNeedStatus.PENDING_REVIEW,
                "notes": "High priority",
            }
        ),
        candidate_needs.create_need(
            {
                "raw_entry_id": other_entry.id,
                "summary": "Collaboration hub",
                "problem_statement": "Remote teams lack context",
                "target_users": "Startup teams",
                "value_proposition": "共享知识库",
                "competition": "Docs",
                "confidence": 0.5,
                "rule_score": 0.45,
                "status": CandidateNeedStatus.APPROVED,
            }
        ),
    ]
    return entry.id, [need.id for need in needs]


def test_create_and_list_candidate_needs(client: TestClient) -> None:
    entry_id, _ = _seed_candidate_needs()

    response = client.post(
        "/api/v1/candidate-needs",
        json={
            "raw_entry_id": entry_id,
            "summary": "Automation insights",
            "problem_statement": "Teams lack automation metrics",
            "status": CandidateNeedStatus.IN_DISCOVERY.value,
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == CandidateNeedStatus.IN_DISCOVERY.value
    assert created["raw_entry_id"] == entry_id
    assert created["rule_score"] is None

    invalid = client.post(
        "/api/v1/candidate-needs",
        json={
            "raw_entry_id": 999,
            "summary": "Invalid",
        },
    )
    assert invalid.status_code == 400

    list_response = client.get(
        "/api/v1/candidate-needs",
        params={"statuses": [CandidateNeedStatus.APPROVED.value]},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == CandidateNeedStatus.APPROVED.value
    assert body["items"][0]["rule_score"] == pytest.approx(0.45)

    search_response = client.get(
        "/api/v1/candidate-needs",
        params={"search": "assistant"},
    )
    assert search_response.status_code == 200
    search_body = search_response.json()
    assert search_body["total"] >= 1
    assert any("assistant" in item["summary"].lower() for item in search_body["items"])


def test_update_candidate_need_and_status(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()

    update_response = client.put(
        f"/api/v1/candidate-needs/{need_ids[0]}",
        json={
            "summary": "Analytics co-pilot",
            "status": CandidateNeedStatus.APPROVED.value,
            "notes": "Ready for review",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["summary"] == "Analytics co-pilot"
    assert updated["status"] == CandidateNeedStatus.APPROVED.value
    assert updated["notes"] == "Ready for review"

    status_response = client.put(
        f"/api/v1/candidate-needs/{need_ids[1]}/status",
        json={"status": CandidateNeedStatus.REJECTED.value},
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == CandidateNeedStatus.REJECTED.value

    missing = client.put(
        "/api/v1/candidate-needs/999/status",
        json={"status": CandidateNeedStatus.APPROVED.value},
    )
    assert missing.status_code == 404


def test_export_candidate_needs(client: TestClient) -> None:
    _seed_candidate_needs()

    json_export = client.get(
        "/api/v1/candidate-needs/export",
        params={"format": "json", "limit": 2},
    )
    assert json_export.status_code == 200
    data = json_export.json()
    assert data["format"] == "json"
    assert len(data["items"]) == 2
    assert data["items"][0]["rule_score"] is not None

    csv_export = client.get(
        "/api/v1/candidate-needs/export",
        params={"format": "csv", "limit": 2},
    )
    assert csv_export.status_code == 200
    csv_body = csv_export.json()
    assert csv_body["format"] == "csv"
    lines = [line for line in csv_body["content"].splitlines() if line]
    assert len(lines) >= 2
    assert "rule_score" in lines[0]


def test_filter_candidate_needs_by_synced_status(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()
    candidate_needs.mark_need_synced(need_ids[0])

    synced_response = client.get("/api/v1/candidate-needs", params={"synced": True})
    assert synced_response.status_code == 200
    synced_body = synced_response.json()
    assert synced_body["total"] == 1
    assert all(item["synced_at"] is not None for item in synced_body["items"])

    unsynced_response = client.get("/api/v1/candidate-needs", params={"synced": False})
    assert unsynced_response.status_code == 200
    unsynced_body = unsynced_response.json()
    assert unsynced_body["total"] == 1
    assert all(item["synced_at"] is None for item in unsynced_body["items"])


def test_candidate_need_status_logs_api(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()

    update_response = client.put(
        f"/api/v1/candidate-needs/{need_ids[0]}/status",
        json={"status": CandidateNeedStatus.APPROVED.value},
    )
    assert update_response.status_code == 200

    logs_response = client.get(
        f"/api/v1/candidate-needs/{need_ids[0]}/status-logs"
    )
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) >= 2
    assert logs[0]["to_status"] == CandidateNeedStatus.PENDING_REVIEW.value
    assert logs[-1]["to_status"] == CandidateNeedStatus.APPROVED.value

    missing = client.get("/api/v1/candidate-needs/999/status-logs")
    assert missing.status_code == 404

    export_response = client.get(
        "/api/v1/candidate-needs/export",
        params={"format": "json", "synced": False},
    )
    assert export_response.status_code == 200
    export_body = export_response.json()
    assert export_body["format"] == "json"
    assert export_body["items"]
    assert all(item["synced_at"] is None for item in export_body["items"])
