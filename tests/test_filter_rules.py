"""筛选规则 API 测试。"""

from __future__ import annotations

import pytest

from app.main import app
from app.services import filter_rules
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    filter_rules.reset_storage()
    yield
    filter_rules.reset_storage()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_filter_rule_crud_flow(client: TestClient) -> None:
    payload = {
        "name": "LLM 筛选",
        "description": "针对 LLM 相关内容的规则",
        "keywords": ["LLM", "大模型"],
        "patterns": ["AI\\s+Ops"],
        "min_score": 0.7,
        "enabled": True,
    }
    response = client.post("/api/v1/filter-rules", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == payload["name"]
    assert created["keywords"] == payload["keywords"]

    rule_id = created["id"]

    detail = client.get(f"/api/v1/filter-rules/{rule_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["min_score"] == pytest.approx(payload["min_score"])

    update = client.put(
        f"/api/v1/filter-rules/{rule_id}",
        json={"enabled": False, "min_score": 0.8},
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["enabled"] is False
    assert updated["min_score"] == pytest.approx(0.8)

    delete = client.delete(f"/api/v1/filter-rules/{rule_id}")
    assert delete.status_code == 204

    missing = client.get(f"/api/v1/filter-rules/{rule_id}")
    assert missing.status_code == 404


def test_filter_rule_filtering(client: TestClient) -> None:
    first = {
        "name": "产品分析", 
        "description": "产品相关关键词",
        "keywords": ["产品", "增长"],
        "min_score": 0.6,
        "enabled": True,
    }
    second = {
        "name": "安全事件",
        "description": "安全告警相关",
        "keywords": ["安全"],
        "enabled": False,
    }
    for payload in (first, second):
        resp = client.post("/api/v1/filter-rules", json=payload)
        assert resp.status_code == 201

    listing = client.get("/api/v1/filter-rules")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2

    enabled_only = client.get("/api/v1/filter-rules", params={"enabled": True})
    assert enabled_only.status_code == 200
    enabled_body = enabled_only.json()
    assert enabled_body["total"] == 1
    assert enabled_body["items"][0]["name"] == first["name"]

    search = client.get("/api/v1/filter-rules", params={"search": "安全"})
    assert search.status_code == 200
    result = search.json()
    assert result["total"] == 1
    assert result["items"][0]["name"] == second["name"]
