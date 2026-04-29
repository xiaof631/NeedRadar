from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.storage import db
from app.main import app
from app.models import FetchStatus
from app.services import rss_sources
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


def test_list_fetch_logs(client: TestClient) -> None:
    source = rss_sources.create_source(
        {
            "name": "Feed",
            "url": "https://example.com/rss",
            "frequency": 3600,
        }
    )

    db.add_fetch_log(source.id, status=FetchStatus.SUCCESS, http_status=200)
    db.add_fetch_log(
        source.id,
        status=FetchStatus.FAILURE,
        http_status=500,
        error_message="server error",
    )

    response = client.get("/api/v1/fetch-logs")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["source_id"] == source.id
    assert body["items"][0]["status"] == FetchStatus.FAILURE.value


def test_filter_fetch_logs_by_source_and_pagination(client: TestClient) -> None:
    first = rss_sources.create_source(
        {
            "name": "First",
            "url": "https://example.com/first.xml",
            "frequency": 3600,
        }
    )
    second = rss_sources.create_source(
        {
            "name": "Second",
            "url": "https://example.com/second.xml",
            "frequency": 3600,
        }
    )

    log1 = db.add_fetch_log(first.id, status=FetchStatus.SUCCESS, http_status=200)
    db.add_fetch_log(first.id, status=FetchStatus.SUCCESS, http_status=200)
    db.add_fetch_log(second.id, status=FetchStatus.FAILURE, http_status=503)

    filtered = client.get(
        "/api/v1/fetch-logs",
        params={"source_id": first.id, "limit": 1},
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["source_id"] == first.id

    second_page = client.get(
        "/api/v1/fetch-logs",
        params={"source_id": first.id, "skip": 1, "limit": 1},
    )
    assert second_page.status_code == 200
    next_body = second_page.json()
    assert next_body["total"] == 2
    assert len(next_body["items"]) == 1
    assert next_body["items"][0]["id"] != body["items"][0]["id"]
    assert next_body["items"][0]["id"] == log1.id


def test_filter_fetch_logs_by_status_and_time_range(client: TestClient) -> None:
    source = rss_sources.create_source(
        {
            "name": "Filter", 
            "url": "https://example.com/filter.xml", 
            "frequency": 3600,
        }
    )

    base_time = datetime.now(UTC)
    _old_log = db.add_fetch_log(source.id, status=FetchStatus.SUCCESS, http_status=200)
    _old_log.fetched_at = base_time - timedelta(hours=3)
    failure_log = db.add_fetch_log(source.id, status=FetchStatus.FAILURE, http_status=500)
    failure_log.fetched_at = base_time - timedelta(hours=1)
    latest_log = db.add_fetch_log(source.id, status=FetchStatus.SUCCESS, http_status=200)
    latest_log.fetched_at = base_time

    status_response = client.get(
        "/api/v1/fetch-logs",
        params={"status": FetchStatus.FAILURE.value},
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["total"] == 1
    assert status_body["items"][0]["id"] == failure_log.id

    time_response = client.get(
        "/api/v1/fetch-logs",
        params={
            "start_fetched_at": (base_time - timedelta(hours=2)).isoformat(),
            "end_fetched_at": base_time.isoformat(),
        },
    )
    assert time_response.status_code == 200
    time_body = time_response.json()
    assert time_body["total"] == 2
    returned_ids = {item["id"] for item in time_body["items"]}
    assert returned_ids == {failure_log.id, latest_log.id}


def test_list_fetch_logs_empty(client: TestClient) -> None:
    response = client.get("/api/v1/fetch-logs")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
