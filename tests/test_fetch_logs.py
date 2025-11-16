from __future__ import annotations

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
