"""筛选规则引擎相关测试。"""

from __future__ import annotations

import pytest

from app.db.storage import db
from app.main import app
from app.models import RawEntryStatus
from app.services import filter_engine, filter_rules, raw_entries
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    db.reset()
    yield
    db.reset()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _create_sample_entry() -> int:
    entry = raw_entries.create_entry(
        {
            "source_id": 1,
            "guid": "guid-1",
            "title": "全新 AI 自动化工具",
            "summary": "这款工具可以帮助产品经理提升效率",
            "content": "介绍了自动化和增长黑客相关技巧",
            "tags": ("AI", "Product"),
            "status": RawEntryStatus.PENDING,
        }
    )
    return entry.id


def _create_rules() -> None:
    filter_rules.create_rule(
        {
            "name": "泛用",
            "keywords": ["工具", "脚本"],
            "patterns": [r"效率"],
            "min_score": 0.2,
            "enabled": True,
        }
    )
    filter_rules.create_rule(
        {
            "name": "自动化热点",
            "keywords": ["AI", "自动化"],
            "patterns": [r"增长\s*黑客"],
            "min_score": 0.5,
            "enabled": True,
        }
    )


def test_evaluate_entry_returns_best_rule() -> None:
    entry_id = _create_sample_entry()
    _create_rules()
    entry = raw_entries.get_entry(entry_id)

    result = filter_engine.evaluate_entry(entry)

    assert result is not None
    assert result.rule.name == "自动化热点"
    assert result.score == pytest.approx(1.0, rel=1e-3)
    assert set(result.matched_keywords) == {"AI", "自动化"}
    assert result.matched_patterns == (r"增长\s*黑客",)
    assert filter_engine.evaluate_entry(entry, min_score=0.9) is not None
    assert filter_engine.evaluate_entry(entry, min_score=1.1) is None


def test_evaluate_entry_api(client: TestClient) -> None:
    entry_id = _create_sample_entry()
    _create_rules()

    response = client.post(f"/api/v1/raw-entries/{entry_id}/evaluate")
    assert response.status_code == 200
    body = response.json()
    assert body["rule_name"] == "自动化热点"
    assert body["matched_keywords"]


def test_evaluate_entry_with_invalid_regex_pattern() -> None:
    entry_id = _create_sample_entry()
    filter_rules.create_rule(
        {
            "name": "Bad Regex",
            "keywords": [],
            "patterns": ["invalid[", r"AI"],
            "min_score": 0.1,
            "enabled": True,
        }
    )
    entry = raw_entries.get_entry(entry_id)
    result = filter_engine.evaluate_entry(entry)
    assert result is not None


def test_evaluate_entry_no_keywords_no_patterns() -> None:
    entry_id = _create_sample_entry()
    filter_rules.create_rule(
        {
            "name": "Empty Rule",
            "keywords": [],
            "patterns": [],
            "min_score": 0.1,
            "enabled": True,
        }
    )
    entry = raw_entries.get_entry(entry_id)
    result = filter_engine.evaluate_entry(entry)
    assert result is None


def test_evaluate_entry_min_score_above_match() -> None:
    entry_id = _create_sample_entry()
    filter_rules.create_rule(
        {
            "name": "Partial Match",
            "keywords": ["AI"],
            "patterns": [],
            "min_score": 0.1,
            "enabled": True,
        }
    )
    entry = raw_entries.get_entry(entry_id)
    result = filter_engine.evaluate_entry(entry)
    assert result is not None
    assert result.rule.name == "Partial Match"
    # Higher function-param min_score should reject the match
    result2 = filter_engine.evaluate_entry(entry, min_score=2.0)
    assert result2 is None


def test_evaluate_entry_with_explicit_empty_rules() -> None:
    entry_id = _create_sample_entry()
    entry = raw_entries.get_entry(entry_id)
    result = filter_engine.evaluate_entry(entry, rules=[])
    assert result is None

