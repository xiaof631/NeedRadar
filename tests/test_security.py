from __future__ import annotations

import os

import pytest

from app.core import config as config_module
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_settings() -> None:
    """确保每个测试后恢复默认配置。"""

    yield
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()
    os.environ.pop("NEEDRADAR_API_TOKENS", None)


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_api_requests_without_token_are_allowed(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard/metrics")

    assert response.status_code == 200


def test_requests_denied_when_token_required(client: TestClient) -> None:
    os.environ["NEEDRADAR_API_TOKENS"] = "secret"
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()

    response = client.get("/api/v1/dashboard/metrics")

    assert response.status_code == 401


def test_requests_with_valid_token_succeed(client: TestClient) -> None:
    os.environ["NEEDRADAR_API_TOKENS"] = "secret,another"
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()

    response = client.get(
        "/api/v1/dashboard/metrics",
        headers={"X-API-Key": "another"},
    )

    assert response.status_code == 200


def test_requests_can_use_query_parameter_token(client: TestClient) -> None:
    os.environ["NEEDRADAR_API_TOKENS"] = "query-token"
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()

    response = client.get(
        "/api/v1/dashboard/metrics",
        params={"api_token": "query-token"},
    )

    assert response.status_code == 200
