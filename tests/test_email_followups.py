from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.main import app
from app.models import CandidateNeedType, SourceType
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


def test_email_followups_builds_marketplace_draft_and_marks_sent(
    client: TestClient,
) -> None:
    source = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://example.com/projects",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "email-marketplace",
            "title": "Python automation dashboard for APAC fulfillment team",
            "summary": "Python automation dashboard for APAC fulfillment team | $2000 | 5 days",
            "content": "Build workflow automation, reporting dashboard, and Dockerized services.",
            "link": "https://example.com/email-marketplace",
            "published_at": datetime(2026, 6, 20, 9, 0, tzinfo=UTC),
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$2000",
                "timeline": "5 days",
                "engagement": "fixed-price",
                "location": "Philippines",
                "skills": ["Python", "Docker"],
            },
        }
    )

    response = client.get(
        "/api/v1/email-followups/",
        params={"source": "marketplace", "min_score": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    task = payload["items"][0]
    assert task["raw_entry_id"] == entry.id
    assert task["status"] == "draft_ready"
    assert task["draft"]["subject"]
    assert "Python automation dashboard" in task["draft"]["body"]
    assert task["draft"]["codex_handoff"].startswith("Use the Gmail connector")

    update_response = client.put(
        f"/api/v1/email-followups/{entry.id}/status",
        json={
            "status": "sent",
            "recipient": "client@example.com",
            "note": "Created Gmail draft and sent after review.",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "sent"
    assert updated["recipient"] == "client@example.com"
    assert updated["next_follow_up_at"] is not None
    assert updated["events"][0]["status_to"] == "sent"

    lead_response = client.get(f"/api/v1/marketplace-leads/{entry.id}")
    assert lead_response.status_code == 200
    lead = lead_response.json()
    assert lead["lead_status"] == "contacted"
    assert lead["follow_up_reason"] == "email_reply_check"


def test_email_followups_includes_customer_radar_opportunity_with_safe_budget_parse(
    client: TestClient,
) -> None:
    source = rss_sources.create_source(
        {
            "name": "DocReview Customer Discovery",
            "url": "https://example.com/docreview",
            "category": "docreview-customer-discovery",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "email-customer-radar",
            "title": "PDF extraction and manual review portal",
            "summary": "Need to extract metadata from PDF files | $8000...",
            "content": (
                "We need someone to parse PDF documents, extract fields into JSON, "
                "sync results to Google Sheets, and manually review records before export."
            ),
            "link": "https://example.com/email-customer-radar",
            "metadata": {"platform": "PeoplePerHour", "budget": "$8000..."},
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "PDF metadata extraction needs a review portal",
            "problem_statement": "Manual PDF review and field copying is slowing the team down.",
            "candidate_type": CandidateNeedType.WORKFLOW_PAIN,
            "review_readiness": 0.9,
            "rule_score": 0.7,
        }
    )

    radar_response = client.get("/api/v1/customer-radar/", params={"min_score": 45})
    assert radar_response.status_code == 200
    assert radar_response.json()["total"] == 1

    response = client.get(
        "/api/v1/email-followups/",
        params={"source": "customer_radar", "min_score": 45},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    task = payload["items"][0]
    assert task["raw_entry_id"] == entry.id
    assert task["source"] == "customer_radar"
    assert task["draft"]["subject"].startswith("Quick idea")
    assert "5-10 real documents" in task["draft"]["body"]
