from __future__ import annotations

import pytest

from app.main import app
from app.models import SourceStatus, SourceType
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


def test_rss_source_crud_flow(client: TestClient) -> None:
    payload = {
        "name": "NeedRadar",
        "url": "https://example.com/rss.xml",
        "category": "tech",
        "frequency": 1800,
    }
    response = client.post("/api/v1/rss-sources", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == payload["name"]
    assert created["status"] == SourceStatus.ACTIVE.value

    source_id = created["id"]
    detail = client.get(f"/api/v1/rss-sources/{source_id}")
    assert detail.status_code == 200
    assert detail.json()["url"] == payload["url"]

    update = client.put(
        f"/api/v1/rss-sources/{source_id}",
        json={"status": SourceStatus.PAUSED.value, "frequency": 7200},
    )
    assert update.status_code == 200
    assert update.json()["status"] == SourceStatus.PAUSED.value
    assert update.json()["frequency"] == 7200

    delete = client.delete(f"/api/v1/rss-sources/{source_id}")
    assert delete.status_code == 204

    missing = client.get(f"/api/v1/rss-sources/{source_id}")
    assert missing.status_code == 404


def test_rss_source_filtering(client: TestClient) -> None:
    first = {
        "name": "AI Weekly",
        "url": "https://feeds.example.com/ai.xml",
        "category": "ai",
        "frequency": 3600,
        "status": SourceStatus.ACTIVE.value,
    }
    second = {
        "name": "Product Digest",
        "url": "https://feeds.example.com/product.xml",
        "category": "product",
        "frequency": 3600,
        "status": SourceStatus.PAUSED.value,
    }
    for item in (first, second):
        resp = client.post("/api/v1/rss-sources", json=item)
        assert resp.status_code == 201

    all_resp = client.get("/api/v1/rss-sources")
    assert all_resp.status_code == 200
    body = all_resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2

    filtered = client.get("/api/v1/rss-sources", params={"status": SourceStatus.PAUSED.value})
    assert filtered.status_code == 200
    paused = filtered.json()
    assert paused["total"] == 1
    assert paused["items"][0]["name"] == second["name"]

    search = client.get("/api/v1/rss-sources", params={"search": "AI"})
    assert search.status_code == 200
    result = search.json()
    assert result["total"] == 1
    assert result["items"][0]["name"] == first["name"]


def test_can_create_and_filter_hacker_news_source(client: TestClient) -> None:
    rss_response = client.post(
        "/api/v1/rss-sources",
        json={
            "name": "AI Weekly",
            "url": "https://feeds.example.com/ai.xml",
            "category": "ai",
            "frequency": 3600,
        },
    )
    assert rss_response.status_code == 201

    hn_payload = {
        "name": "Ask HN",
        "url": "https://hacker-news.firebaseio.com/v0/askstories.json",
        "category": "community",
        "frequency": 900,
        "source_type": SourceType.HACKER_NEWS.value,
        "config": {"item_limit": 5},
    }
    hn_response = client.post("/api/v1/rss-sources", json=hn_payload)
    assert hn_response.status_code == 201
    body = hn_response.json()
    assert body["source_type"] == SourceType.HACKER_NEWS.value
    assert body["config"]["item_limit"] == 5

    filtered = client.get(
        "/api/v1/rss-sources",
        params={"source_type": SourceType.HACKER_NEWS.value},
    )
    assert filtered.status_code == 200
    result = filtered.json()
    assert result["total"] == 1
    assert result["items"][0]["name"] == hn_payload["name"]


def test_can_create_and_filter_github_issues_source(client: TestClient) -> None:
    payload = {
        "name": "NeedRadar Repo Issues",
        "url": "https://api.github.com/repos/acme/needradar/issues",
        "category": "developer-tools",
        "frequency": 1200,
        "source_type": SourceType.GITHUB_ISSUES.value,
        "config": {"item_limit": 10, "state": "open"},
    }
    response = client.post("/api/v1/rss-sources", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == SourceType.GITHUB_ISSUES.value
    assert body["config"]["state"] == "open"

    filtered = client.get(
        "/api/v1/rss-sources",
        params={"source_type": SourceType.GITHUB_ISSUES.value},
    )
    assert filtered.status_code == 200
    result = filtered.json()
    assert result["total"] == 1
    assert result["items"][0]["url"] == payload["url"]


def test_can_create_and_filter_reddit_source(client: TestClient) -> None:
    payload = {
        "name": "r/startups new",
        "url": "https://www.reddit.com/r/startups/new",
        "category": "community",
        "frequency": 1200,
        "source_type": SourceType.REDDIT.value,
        "config": {"item_limit": 10, "time": "week"},
    }
    response = client.post("/api/v1/rss-sources", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == SourceType.REDDIT.value
    assert body["config"]["time"] == "week"

    filtered = client.get(
        "/api/v1/rss-sources",
        params={"source_type": SourceType.REDDIT.value},
    )
    assert filtered.status_code == 200
    result = filtered.json()
    assert result["total"] == 1
    assert result["items"][0]["name"] == payload["name"]


def test_can_create_reddit_comments_source(client: TestClient) -> None:
    payload = {
        "name": "r/startups comments",
        "url": "https://www.reddit.com/r/startups/comments",
        "category": "community",
        "frequency": 900,
        "source_type": SourceType.REDDIT.value,
        "config": {"item_limit": 25, "sort": "new"},
    }
    response = client.post("/api/v1/rss-sources", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == SourceType.REDDIT.value
    assert body["config"]["sort"] == "new"
    assert body["config"]["item_limit"] == 25


def test_can_create_and_filter_youtube_source(client: TestClient) -> None:
    payload = {
        "name": "YouTube workflow search",
        "url": "https://www.googleapis.com/youtube/v3/search",
        "category": "video",
        "frequency": 1800,
        "source_type": SourceType.YOUTUBE.value,
        "config": {"query": "manual workflow automation", "item_limit": 10},
    }
    response = client.post("/api/v1/rss-sources", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == SourceType.YOUTUBE.value
    assert body["config"]["query"] == "manual workflow automation"

    filtered = client.get(
        "/api/v1/rss-sources",
        params={"source_type": SourceType.YOUTUBE.value},
    )
    assert filtered.status_code == 200
    result = filtered.json()
    assert result["total"] == 1
    assert result["items"][0]["name"] == payload["name"]
