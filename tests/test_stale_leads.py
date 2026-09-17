from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models import CandidateNeedStatus, RawEntryStatus, SourceType
from app.services import (
    candidate_needs,
    marketplace_leads,
    raw_entries,
    rss_sources,
    stale_leads,
)


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()


def _entry(
    *,
    source_id: int,
    guid: str,
    published_at: datetime,
    status: RawEntryStatus = RawEntryStatus.PENDING,
    metadata: dict[str, object] | None = None,
):
    return raw_entries.create_entry(
        {
            "source_id": source_id,
            "guid": guid,
            "title": f"Lead {guid}",
            "summary": f"Opportunity {guid}",
            "published_at": published_at,
            "status": status,
            "metadata": metadata or {},
        }
    )


def test_archive_stale_leads_is_safe_visible_and_idempotent() -> None:
    now = datetime(2026, 7, 25, 8, 0, tzinfo=UTC)
    source = rss_sources.create_source(
        {
            "name": "Signals",
            "url": "https://example.com/signals.xml",
            "source_type": SourceType.RSS,
        }
    )
    marketplace = rss_sources.create_source(
        {
            "name": "Freelancer Projects",
            "url": "https://example.com/freelancer",
            "source_type": SourceType.FREELANCE_MARKETPLACE,
        }
    )

    stale_pending = _entry(
        source_id=source.id,
        guid="stale-pending",
        published_at=now - timedelta(days=8),
    )
    boundary = _entry(
        source_id=source.id,
        guid="boundary",
        published_at=now - timedelta(days=7),
    )
    processed = _entry(
        source_id=source.id,
        guid="processed",
        published_at=now - timedelta(days=30),
        status=RawEntryStatus.FILTERED,
    )
    stale_promoted = _entry(
        source_id=source.id,
        guid="stale-promoted",
        published_at=now - timedelta(days=10),
        status=RawEntryStatus.PROMOTED,
    )
    stale_candidate = candidate_needs.create_need(
        {
            "raw_entry_id": stale_promoted.id,
            "summary": "Stale candidate",
            "status": CandidateNeedStatus.PENDING_REVIEW,
        }
    )
    approved_entry = _entry(
        source_id=source.id,
        guid="approved",
        published_at=now - timedelta(days=20),
        status=RawEntryStatus.PROMOTED,
    )
    approved_candidate = candidate_needs.create_need(
        {
            "raw_entry_id": approved_entry.id,
            "summary": "Approved candidate",
            "status": CandidateNeedStatus.APPROVED,
        }
    )
    stale_marketplace = _entry(
        source_id=marketplace.id,
        guid="stale-marketplace",
        published_at=now - timedelta(days=8),
    )
    watching_marketplace = _entry(
        source_id=marketplace.id,
        guid="watching-marketplace",
        published_at=now - timedelta(days=30),
        metadata={"lead_status": "watching"},
    )
    resolved_marketplace = _entry(
        source_id=marketplace.id,
        guid="resolved-marketplace",
        published_at=now - timedelta(days=30),
        metadata={"lead_outcome": "won"},
    )

    result = stale_leads.archive_stale_leads(stale_after_days=7, now=now)

    assert result.raw_entries_archived == 3
    assert result.candidate_needs_archived == 1
    assert raw_entries.get_entry(stale_pending.id).status == RawEntryStatus.ARCHIVED
    assert raw_entries.get_entry(stale_promoted.id).status == RawEntryStatus.ARCHIVED
    assert raw_entries.get_entry(stale_marketplace.id).status == RawEntryStatus.ARCHIVED
    assert raw_entries.get_entry(boundary.id).status == RawEntryStatus.PENDING
    assert raw_entries.get_entry(processed.id).status == RawEntryStatus.FILTERED
    assert raw_entries.get_entry(approved_entry.id).status == RawEntryStatus.PROMOTED
    assert raw_entries.get_entry(watching_marketplace.id).status == RawEntryStatus.PENDING
    assert raw_entries.get_entry(resolved_marketplace.id).status == RawEntryStatus.PENDING
    assert candidate_needs.get_need(stale_candidate.id).status == CandidateNeedStatus.ARCHIVED
    assert candidate_needs.get_need(approved_candidate.id).status == CandidateNeedStatus.APPROVED

    active_raw_total, _ = raw_entries.list_entries()
    archived_raw_total, archived_raw = raw_entries.list_entries(
        status=RawEntryStatus.ARCHIVED
    )
    assert active_raw_total == 5
    assert archived_raw_total == 3
    assert {item.id for item in archived_raw} == {
        stale_pending.id,
        stale_promoted.id,
        stale_marketplace.id,
    }

    active_need_total, _ = candidate_needs.list_needs()
    archived_need_total, archived_needs = candidate_needs.list_needs(
        statuses=(CandidateNeedStatus.ARCHIVED,)
    )
    assert active_need_total == 1
    assert archived_need_total == 1
    assert archived_needs[0].id == stale_candidate.id

    default_marketplace = marketplace_leads.query_leads(limit=20)
    archived_marketplace = marketplace_leads.query_leads(
        lead_status=marketplace_leads.MarketplaceLeadStatus.ARCHIVED,
        limit=20,
    )
    assert {item.id for item in default_marketplace.items} == {
        watching_marketplace.id,
        resolved_marketplace.id,
    }
    assert [item.id for item in archived_marketplace.items] == [stale_marketplace.id]

    logs = candidate_needs.list_need_status_logs(stale_candidate.id)
    archive_logs = [
        item for item in logs if item.to_status == CandidateNeedStatus.ARCHIVED
    ]
    assert len(archive_logs) == 1
    assert archive_logs[0].note == stale_leads.STALE_ARCHIVE_REASON

    repeated = stale_leads.archive_stale_leads(stale_after_days=7, now=now)
    assert repeated.raw_entries_archived == 0
    assert repeated.candidate_needs_archived == 0
    assert len(candidate_needs.list_need_status_logs(stale_candidate.id)) == len(logs)
