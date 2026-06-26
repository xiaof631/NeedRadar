from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.main import app
from app.models import CandidateNeedType, SourceType
from app.services import candidate_needs, customer_radar, raw_entries, rss_sources
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


def test_customer_radar_scores_document_review_opportunity(client: TestClient) -> None:
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
            "guid": "pdf-review",
            "title": "PDF Scraping and Data Review Interface",
            "summary": "PDF scraping MVP | $500",
            "content": (
                "We need to scrape PDF files, extract text and metadata into a database, "
                "then manually inspect extracted records in a simple review UI before export."
            ),
            "link": "https://example.com/pdf-review",
            "published_at": datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
            "metadata": {"platform": "PeoplePerHour", "budget": "$500"},
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "PDF extraction needs a manual review interface",
            "problem_statement": "Manual inspection of extracted PDF text is required before export.",
            "candidate_type": CandidateNeedType.WORKFLOW_PAIN,
            "review_readiness": 0.8,
            "rule_score": 0.6,
        }
    )

    response = client.get("/api/v1/customer-radar/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["title"] == "PDF Scraping and Data Review Interface"
    assert item["fit_score"] >= 78
    assert item["credibility_score"] >= 75
    assert item["credibility_level"] == "high"
    assert item["credibility_reasons"]
    assert item["recommended_action"] == "contact_now"
    assert item["customer_segment"] == "document_ops"
    assert "manual_review" in item["matched_signals"]
    assert item["budget_signal"] == "$500"
    assert "5-10 real documents" in item["outreach_draft"]
    assert payload["summary"]["contact_now"] == 1
    assert payload["summary"]["average_credibility_score"] >= 75


def test_customer_radar_can_filter_segment_and_search() -> None:
    source = rss_sources.create_source(
        {
            "name": "Reddit SaaS",
            "url": "https://example.com/reddit",
            "frequency": 3600,
            "source_type": SourceType.REDDIT,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "council-docs",
            "title": "Council document AI query platform",
            "summary": "Looking for a way to crawl council minutes and policy PDFs.",
            "content": "Manual review of planning agenda PDFs is slow and error prone.",
            "link": "https://example.com/council",
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "Council PDFs need extraction and review",
            "problem_statement": "Teams manually read council planning documents and copy fields.",
            "candidate_type": CandidateNeedType.WORKFLOW_PAIN,
            "review_readiness": 0.9,
        }
    )

    result = customer_radar.query_opportunities(
        segment=customer_radar.CustomerSegment.GOVERNMENT_DOCS,
        search="planning",
        min_score=40,
    )

    assert result.total == 1
    assert result.items[0].customer_segment == customer_radar.CustomerSegment.GOVERNMENT_DOCS
    assert result.summary.segment_breakdown["government_docs"] == 1


def test_customer_radar_default_query_shows_doc_opportunities_before_noise() -> None:
    source = rss_sources.create_source(
        {
            "name": "Mixed leads",
            "url": "https://example.com/mixed",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
        }
    )
    doc_entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "drive-sheets",
            "title": "Google Drive PDF metadata to Google Sheets",
            "summary": "Need PDF extraction and validation | $300",
            "content": (
                "We manually review property PDF documents, extract fields, "
                "and sync validated data into Google Sheets."
            ),
            "metadata": {"platform": "PeoplePerHour", "budget": "$300"},
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": doc_entry.id,
            "summary": "Property documents need extraction and review",
            "problem_statement": "Manual PDF review and field copying is slow.",
            "candidate_type": CandidateNeedType.WORKFLOW_PAIN,
            "review_readiness": 0.85,
            "rule_score": 0.65,
        }
    )
    noise_entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "brand-design",
            "title": "Need a logo redesign",
            "summary": "Looking for branding help",
            "content": "We need a modern visual identity and homepage graphics.",
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": noise_entry.id,
            "summary": "Branding work request",
            "candidate_type": CandidateNeedType.MARKET_SIGNAL,
        }
    )

    result = customer_radar.query_opportunities()

    assert result.total == 1
    assert result.items[0].title == "Google Drive PDF metadata to Google Sheets"


def test_customer_radar_downgrades_low_budget_one_off_tasks() -> None:
    source = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://example.com/pph-low-budget",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "flipbook",
            "title": "Extract a Flipbook Catalog",
            "summary": "Extract a Flipbook Catalog | $10",
            "content": (
                "Looking to extract a Flipbook Catalog and convert into a pdf "
                "that I can download."
            ),
            "metadata": {"platform": "PeoplePerHour", "budget": "$10"},
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "Catalog extraction one-off task",
            "candidate_type": CandidateNeedType.TOOL_SEEKING,
            "review_readiness": 0.8,
            "rule_score": 0.6,
        }
    )

    result = customer_radar.query_opportunities(min_score=70)

    assert result.total == 1
    item = result.items[0]
    assert item.fit_score >= 70
    assert item.credibility_level == customer_radar.CredibilityLevel.LOW
    assert item.recommended_action == customer_radar.RecommendedAction.WATCH
    assert any("预算极低" in flag for flag in item.risk_flags)
