from __future__ import annotations

import asyncio

import httpx
import pytest

from app.db.storage import db
from app.models import (
    CandidateNeed,
    CandidateNeedStatus,
    FilterRule,
    RawEntryStatus,
    SourceStatus,
)
from app.services import candidate_needs, raw_entries, rss_fetcher, rss_sources
from app.services.filter_engine import RuleMatchResult
from app.services.llm_client import StructuredNeed
from app.services.pipeline import EntryNotQualifiedError, PromotionResult
from jobs import tasks


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    db.reset()
    yield
    db.reset()


def test_fetch_active_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    source_active = rss_sources.create_source(
        {"name": "A", "url": "https://example.com/a", "frequency": 3600}
    )
    rss_sources.create_source(
        {
            "name": "B",
            "url": "https://example.com/b",
            "frequency": 3600,
            "status": SourceStatus.PAUSED,
        }
    )

    called: list[int] = []

    async def _fake_fetch(source_id: int, *, client: object) -> rss_fetcher.FetchResult:
        called.append(source_id)
        return rss_fetcher.FetchResult(
            source_id=source_id,
            fetched_entries=3,
            new_entries=1,
            status=rss_fetcher.FetchStatus.SUCCESS,
        )

    monkeypatch.setattr(rss_fetcher, "fetch_rss_source", _fake_fetch)

    results = asyncio.run(tasks.fetch_active_sources())

    assert called == [source_active.id]
    assert len(results) == 1
    assert results[0].source_id == source_active.id


def test_promote_pending_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_pending = raw_entries.create_entry(
        {
            "source_id": 1,
            "guid": "guid-1",
            "title": "Alpha",
            "status": RawEntryStatus.PENDING,
        }
    )
    raw_entries.create_entry(
        {
            "source_id": 1,
            "guid": "guid-2",
            "title": "Beta",
            "status": RawEntryStatus.IGNORED,
        }
    )
    entry_pending_second = raw_entries.create_entry(
        {
            "source_id": 1,
            "guid": "guid-3",
            "title": "Gamma",
            "status": RawEntryStatus.PENDING,
        }
    )

    def _build_result(entry_id: int) -> PromotionResult:
        entry = raw_entries.get_entry(entry_id)
        candidate = CandidateNeed(
            id=entry_id,
            raw_entry_id=entry.id,
            summary=entry.title,
            status=CandidateNeedStatus.PENDING_REVIEW,
        )
        rule = FilterRule(
            id=1,
            name="demo",
            description=None,
            keywords=("demo",),
            patterns=(),
            min_score=0.1,
            enabled=True,
        )
        match = RuleMatchResult(
            rule=rule,
            score=1.0,
            matched_keywords=("demo",),
            matched_patterns=(),
        )
        return PromotionResult(
            entry=entry,
            candidate_need=candidate,
            rule_match=match,
            structured_need=StructuredNeed(summary="demo"),
        )

    def _fake_promote(entry_id: int, *, min_score: float | None) -> PromotionResult:
        if entry_id == entry_pending_second.id:
            raise EntryNotQualifiedError
        return _build_result(entry_id)

    monkeypatch.setattr(tasks.pipeline, "promote_entry", _fake_promote)

    results = tasks.promote_pending_entries(batch_size=5, min_score=0.5)

    assert len(results) == 1
    assert results[0].entry.id == entry_pending.id


def _seed_candidate_need(status: CandidateNeedStatus = CandidateNeedStatus.APPROVED) -> CandidateNeed:
    source = rss_sources.create_source(
        {"name": "Seed", "url": "https://example.com/rss", "frequency": 3600}
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "seed-guid",
            "title": "Seed entry",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    return candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "Demo need",
            "status": status,
        }
    )


class _DummyResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _DummyClient:
    def __init__(self, response: _DummyResponse | None = None) -> None:
        self.response = response or _DummyResponse(200)
        self.closed = False
        self.payloads: list[dict] = []

    async def post(self, url: str, json: dict) -> _DummyResponse:
        self.payloads.append(json)
        return self.response

    async def aclose(self) -> None:
        self.closed = True


def test_sync_new_candidate_needs_success() -> None:
    need = _seed_candidate_need()
    client = _DummyClient()

    results = asyncio.run(
        tasks.sync_new_candidate_needs(
            webhook_url="https://hook.example.com",
            statuses=(CandidateNeedStatus.APPROVED,),
            batch_size=5,
            client=client,
        )
    )

    assert len(results) == 1
    assert results[0].success is True
    refreshed = candidate_needs.get_need(need.id)
    assert refreshed.synced_at is not None
    assert refreshed.sync_error is None
    assert client.closed is False


def test_sync_new_candidate_needs_handles_http_error() -> None:
    need = _seed_candidate_need()

    class _ErrorClient(_DummyClient):
        async def post(self, url: str, json: dict) -> _DummyResponse:  # type: ignore[override]
            raise httpx.HTTPError("network error")

    client = _ErrorClient()

    results = asyncio.run(
        tasks.sync_new_candidate_needs(
            webhook_url="https://hook.example.com",
            statuses=(CandidateNeedStatus.APPROVED,),
            batch_size=5,
            client=client,
        )
    )

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error is not None
    refreshed = candidate_needs.get_need(need.id)
    assert refreshed.synced_at is None
    assert refreshed.sync_error is not None


def test_sync_new_candidate_needs_handles_non_2xx() -> None:
    need = _seed_candidate_need()
    client = _DummyClient(response=_DummyResponse(503))

    results = asyncio.run(
        tasks.sync_new_candidate_needs(
            webhook_url="https://hook.example.com",
            statuses=(CandidateNeedStatus.APPROVED,),
            batch_size=5,
            client=client,
        )
    )

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].status_code == 503
    refreshed = candidate_needs.get_need(need.id)
    assert refreshed.synced_at is None
    assert refreshed.sync_error == "HTTP 503"
