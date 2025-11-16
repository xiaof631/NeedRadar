from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.main import app
from app.models import RawEntryStatus, SourceStatus
from app.services import raw_entries, rss_sources
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


def _seed_entries() -> tuple[int, list[int]]:
    source = rss_sources.create_source(
        {
            "name": "Tech", 
            "url": "https://example.com/tech.xml", 
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
        }
    )
    other = rss_sources.create_source(
        {
            "name": "News",
            "url": "https://example.com/news.xml",
            "frequency": 7200,
            "status": SourceStatus.PAUSED,
        }
    )
    now = datetime.now(UTC)
    entries = [
        raw_entries.create_entry(
            {
                "source_id": source.id,
                "guid": "entry-1",
                "title": "AI Weekly",
                "summary": "AI tooling roundup",
                "published_at": now - timedelta(days=1),
                "tags": ["ai"],
                "status": RawEntryStatus.PENDING,
            }
        ),
        raw_entries.create_entry(
            {
                "source_id": source.id,
                "guid": "entry-2",
                "title": "Product Digest",
                "summary": "Product analytics news",
                "published_at": now - timedelta(days=2),
                "tags": ["product"],
                "status": RawEntryStatus.IGNORED,
            }
        ),
        raw_entries.create_entry(
            {
                "source_id": other.id,
                "guid": "entry-3",
                "title": "Community Updates",
                "summary": "Community highlight",
                "published_at": now,
                "tags": ["community"],
                "status": RawEntryStatus.FILTERED,
            }
        ),
    ]
    return source.id, [entry.id for entry in entries]


def test_list_raw_entries_with_filters(client: TestClient) -> None:
    source_id, entry_ids = _seed_entries()

    response = client.get("/api/v1/raw-entries", params={"limit": 10})
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 3

    status_response = client.get(
        "/api/v1/raw-entries",
        params={"status": RawEntryStatus.IGNORED.value, "limit": 10},
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["total"] == 1
    assert status_body["items"][0]["id"] == entry_ids[1]

    search_response = client.get(
        "/api/v1/raw-entries",
        params={"search": "AI", "limit": 10},
    )
    assert search_response.status_code == 200
    search_body = search_response.json()
    assert search_body["total"] == 1
    assert search_body["items"][0]["id"] == entry_ids[0]

    time_filter = client.get(
        "/api/v1/raw-entries",
        params={
            "source_id": source_id,
            "start_published_at": (datetime.now(UTC) - timedelta(days=2, hours=12)).isoformat(),
            "end_published_at": (datetime.now(UTC) - timedelta(hours=6)).isoformat(),
            "limit": 10,
        },
    )
    assert time_filter.status_code == 200
    time_body = time_filter.json()
    assert time_body["total"] == 2
    assert {item["id"] for item in time_body["items"]} == {entry_ids[0], entry_ids[1]}


def test_update_raw_entry_status(client: TestClient) -> None:
    _, entry_ids = _seed_entries()

    response = client.put(
        f"/api/v1/raw-entries/{entry_ids[0]}/status",
        json={"status": RawEntryStatus.IGNORED.value},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == RawEntryStatus.IGNORED.value

    missing = client.put(
        "/api/v1/raw-entries/999/status",
        json={"status": RawEntryStatus.FILTERED.value},
    )
    assert missing.status_code == 404


def test_bulk_update_status(client: TestClient) -> None:
    _, entry_ids = _seed_entries()

    response = client.post(
        "/api/v1/raw-entries/bulk-status",
        json={"ids": entry_ids[:2], "status": RawEntryStatus.FILTERED.value},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert all(item["status"] == RawEntryStatus.FILTERED.value for item in body)

    missing = client.post(
        "/api/v1/raw-entries/bulk-status",
        json={"ids": [999], "status": RawEntryStatus.PROMOTED.value},
    )
    assert missing.status_code == 404


def test_export_raw_entries(client: TestClient) -> None:
    _, entry_ids = _seed_entries()

    json_export = client.get(
        "/api/v1/raw-entries/export",
        params={"format": "json", "limit": 2},
    )
    assert json_export.status_code == 200
    data = json_export.json()
    assert data["format"] == "json"
    items = data["items"]
    assert len(items) == 2
    assert {item["id"] for item in items}.issubset(set(entry_ids))

    csv_export = client.get(
        "/api/v1/raw-entries/export",
        params={"format": "csv", "limit": 2},
    )
    assert csv_export.status_code == 200
    csv_body = csv_export.json()
    assert csv_body["format"] == "csv"
    lines = [line for line in csv_body["content"].splitlines() if line]
    assert len(lines) >= 2
    assert lines[0].startswith("id,source_id")


def test_raw_entry_content_hash_and_duplicate_detection(client: TestClient) -> None:
    source = rss_sources.create_source(
        {
            "name": "Hash",
            "url": "https://example.com/hash.xml",
            "frequency": 1800,
            "status": SourceStatus.ACTIVE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "hash-1",
            "title": "NeedRadar Intro",
            "summary": "All about the same idea",
            "link": "https://example.com/posts/1",
            "status": RawEntryStatus.PENDING,
        }
    )
    assert entry.content_hash is not None

    with pytest.raises(raw_entries.RawEntryAlreadyExistsError):
        raw_entries.create_entry(
            {
                "source_id": source.id,
                "guid": "hash-1",
                "title": "Duplicated",
                "summary": "Another text",
                "link": "https://example.com/posts/1",
                "status": RawEntryStatus.PENDING,
            }
        )

    with pytest.raises(raw_entries.RawEntryAlreadyExistsError):
        raw_entries.create_entry(
            {
                "source_id": source.id,
                "guid": "hash-2",
                "title": "NeedRadar Intro",
                "summary": "All about   the same idea",  # 与原始条目等价
                "link": "https://example.com/posts/1",
                "status": RawEntryStatus.PENDING,
            }
        )

    response = client.get("/api/v1/raw-entries", params={"limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["content_hash"] == entry.content_hash
