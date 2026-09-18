"""关键词种子抽取与验证测试。"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import httpx
import pytest

from app.db.storage import db
from app.main import app
from app.models import KeywordSeedStatus
from app.services import keyword_seeds
from app.services.keyword_provider import (
    AutocompleteProvider,
    DataForSEOProvider,
    KeywordMetrics,
    KeywordProviderError,
    KeywordRateLimitedError,
)
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


# ── 纯函数抽取测试 ──────────────────────────────────────────────


def test_extract_phrases_english_patterns() -> None:
    text = "I need to convert bank statement PDF to Excel every month."
    phrases = keyword_seeds.extract_phrases(text)
    assert ("convert bank statement pdf to excel", "convert_to") in phrases

    text = "Looking for a pdf to excel converter that keeps tables."
    phrases = keyword_seeds.extract_phrases(text)
    assert ("pdf to excel converter", "to_converter") in phrases

    text = "We extract invoice fields from scanned documents manually."
    phrases = keyword_seeds.extract_phrases(text)
    assert ("extract invoice fields from scanned documents", "extract_from") in phrases

    text = "Anyone knows a good receipt extractor for expense reports?"
    phrases = keyword_seeds.extract_phrases(text)
    assert ("receipt extractor", "extractor") in phrases

    text = "Need a script to scrape product prices from listings."
    phrases = keyword_seeds.extract_phrases(text)
    assert ("scrape product prices", "scrape_target") in phrases


def test_extract_phrases_chinese_patterns() -> None:
    phrases = keyword_seeds.extract_phrases("有没有工具能把银行流水转成Excel表格")
    assert ("银行流水转成excel表格", "zh_convert_to") in phrases

    phrases = keyword_seeds.extract_phrases("需要从PDF中提取表格数据")
    assert ("从pdf提取表格数据", "zh_extract_from") in phrases


def test_extract_phrases_filters_filler_and_length() -> None:
    # 槽位全是功能词的匹配应被丢弃
    assert ("convert it to excel", "convert_to") not in keyword_seeds.extract_phrases(
        "convert it to excel"
    )
    # 过短的短语应被丢弃（长度不足 8 字符）
    assert ("scrape it", "scrape_target") not in keyword_seeds.extract_phrases("scrape it")


def test_extract_phrases_dedupes_within_text() -> None:
    text = "convert pdf to excel and also convert PDF to Excel again"
    phrases = keyword_seeds.extract_phrases(text)
    keys = [keyword_seeds.phrase_key(phrase) for phrase, _ in phrases]
    assert len(keys) == len(set(keys))


# ── 抽取入库与证据合并 ──────────────────────────────────────────


def _create_need(source_name: str, title: str, content: str) -> None:
    source = db.create_source(
        {"name": source_name, "url": f"https://example.com/{source_name}"}
    )
    entry_payload = {
        "source_id": source.id,
        "guid": f"guid-{source_name}-{title[:12]}",
        "title": title,
        "content": content,
    }
    entry_payload["content_hash"] = f"hash-{source_name}-{title[:12]}"
    entry = db.create_raw_entry(entry_payload)
    db.create_candidate_need(
        {
            "raw_entry_id": entry.id,
            "summary": title,
        }
    )


def test_extract_seeds_creates_and_merges_evidence() -> None:
    _create_need(
        "Freelancer PDF Jobs",
        "Convert Medical PDFs to Excel",
        "Need someone to convert medical pdfs to excel weekly.",
    )
    result = keyword_seeds.extract_seeds()
    assert result.scanned == 1
    assert result.created >= 1

    seed = db.get_keyword_seed_by_key("convert medical pdfs to excel")
    assert seed is not None
    assert seed.occurrence_count == 1
    assert len(seed.evidence) == 1
    assert seed.evidence[0]["source_name"] == "Freelancer PDF Jobs"
    assert seed.opportunity_score > 0

    # 另一条目提到相同短语：合并证据
    _create_need(
        "PeoplePerHour",
        "Medical PDF conversion",
        "Please convert medical pdfs to excel for our clinic.",
    )
    result = keyword_seeds.extract_seeds()
    assert result.merged >= 1
    seed = db.get_keyword_seed_by_key("convert medical pdfs to excel")
    assert seed is not None
    assert seed.occurrence_count == 2
    assert len(seed.evidence) == 2

    # 重复运行幂等：出现次数与证据不再增长
    keyword_seeds.extract_seeds()
    seed = db.get_keyword_seed_by_key("convert medical pdfs to excel")
    assert seed is not None
    assert seed.occurrence_count == 2


def test_opportunity_score_evidence_boundaries() -> None:
    assert keyword_seeds._evidence_score(1, [{"source_name": "a"}]) == 18
    # 出现次数与多来源加成封顶 50
    evidence = [{"source_name": f"src-{i}"} for i in range(10)]
    assert keyword_seeds._evidence_score(100, evidence) == 50


def test_keyword_score_buckets() -> None:
    seed = db.create_keyword_seed(
        {"phrase": "pdf to excel", "phrase_key": "pdf to excel", "pattern_kind": "to_converter"}
    )

    def _with_metrics(volume: int, difficulty: int | None) -> int:
        seed.search_volume = volume
        seed.keyword_difficulty = difficulty
        return keyword_seeds._keyword_score(seed)

    assert _with_metrics(0, None) == 0
    assert _with_metrics(5, None) == 8
    assert _with_metrics(50, None) == 16
    assert _with_metrics(500, None) == 24
    assert _with_metrics(5_000, None) == 32
    assert _with_metrics(50_000, None) == 40
    assert _with_metrics(500_000, None) == 40
    # 难度越低加分越高，关键词部分封顶 50
    assert _with_metrics(500_000, 0) == 50


# ── 验证流程（Provider）────────────────────────────────────────


class _FakeProvider:
    def __init__(self, metrics_map: dict[str, KeywordMetrics] | None = None) -> None:
        self.metrics_map = metrics_map or {}
        self.requested: list[Sequence[str]] = []

    async def fetch_metrics(self, phrases: Sequence[str]) -> dict[str, KeywordMetrics]:
        self.requested.append(list(phrases))
        return self.metrics_map


def test_validate_pending_without_provider_skips(monkeypatch) -> None:
    db.create_keyword_seed(
        {"phrase": "pdf to excel", "phrase_key": "pdf to excel", "pattern_kind": "to_converter"}
    )
    monkeypatch.setattr(keyword_seeds, "resolve_keyword_provider", lambda: None)
    result = asyncio.run(keyword_seeds.validate_pending())
    assert result.validated == 0
    assert result.reason == "keyword provider not configured"


def test_validate_pending_marks_validated_and_no_volume(monkeypatch) -> None:
    db.create_keyword_seed(
        {"phrase": "pdf to excel", "phrase_key": "pdf to excel", "pattern_kind": "to_converter"}
    )
    db.create_keyword_seed(
        {"phrase": "obscure phrase", "phrase_key": "obscure phrase", "pattern_kind": "convert_to"}
    )
    provider = _FakeProvider(
        {
            "pdf to excel": KeywordMetrics(
                search_volume=1200, keyword_difficulty=30, cpc=1.25, competition="low"
            )
        }
    )
    monkeypatch.setattr(keyword_seeds, "resolve_keyword_provider", lambda: provider)


    result = asyncio.run(keyword_seeds.validate_pending())
    assert result.validated == 1
    assert result.no_volume == 1

    validated = db.get_keyword_seed_by_key("pdf to excel")
    assert validated is not None
    assert validated.status == KeywordSeedStatus.VALIDATED
    assert validated.search_volume == 1200
    assert validated.validated_at is not None

    no_volume = db.get_keyword_seed_by_key("obscure phrase")
    assert no_volume is not None
    assert no_volume.status == KeywordSeedStatus.NO_VOLUME
    assert no_volume.search_volume == 0


def test_validate_pending_confirmed_without_volume_counts_as_validated(monkeypatch) -> None:
    """免费 suggest 校验确认存在的短语应标记 validated 且机会分获得加分。"""

    db.create_keyword_seed(
        {"phrase": "pdf to excel", "phrase_key": "pdf to excel", "pattern_kind": "to_converter"}
    )
    provider = _FakeProvider(
        {"pdf to excel": KeywordMetrics(search_volume=None, competition="confirmed_by_suggest")}
    )
    monkeypatch.setattr(keyword_seeds, "resolve_keyword_provider", lambda: provider)

    result = asyncio.run(keyword_seeds.validate_pending())
    assert result.validated == 1
    assert result.no_volume == 0

    seed = db.get_keyword_seed_by_key("pdf to excel")
    assert seed is not None
    assert seed.status == KeywordSeedStatus.VALIDATED
    assert seed.search_volume is None
    assert seed.competition == "confirmed_by_suggest"
    evidence_score = keyword_seeds._evidence_score(1, seed.evidence)
    assert seed.opportunity_score == min(100, evidence_score + 10)


def test_validate_pending_provider_error_marks_seeds(monkeypatch) -> None:
    db.create_keyword_seed(
        {"phrase": "pdf to excel", "phrase_key": "pdf to excel", "pattern_kind": "to_converter"}
    )

    class _BrokenProvider:
        async def fetch_metrics(self, phrases: Sequence[str]) -> dict[str, KeywordMetrics]:
            raise KeywordProviderError("boom")

    monkeypatch.setattr(keyword_seeds, "resolve_keyword_provider", lambda: _BrokenProvider())


    result = asyncio.run(keyword_seeds.validate_pending())
    assert result.errors == 1
    seed = db.get_keyword_seed_by_key("pdf to excel")
    assert seed is not None
    assert seed.status == KeywordSeedStatus.ERROR
    assert "boom" in (seed.validation_error or "")


# ── DataForSEO 客户端 ───────────────────────────────────────────


def _dataforseo_client(handler) -> DataForSEOProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return DataForSEOProvider(login="u", password="p", client=client)


def test_dataforseo_provider_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host in {"api.dataforseo.com", "sandbox.dataforseo.com"}
        return httpx.Response(
            200,
            json={
                "status_code": 20000,
                "tasks": [
                    {
                        "status_code": 20000,
                        "result": [
                            {
                                "keyword": "PDF to Excel",
                                "search_volume": 5400,
                                "keyword_difficulty": 42,
                                "cpc": 2.31,
                                "competition": 0.2,
                            }
                        ],
                    }
                ],
            },
        )


    provider = _dataforseo_client(handler)
    metrics = asyncio.run(provider.fetch_metrics(["pdf to excel"]))
    assert metrics["pdf to excel"].search_volume == 5400
    assert metrics["pdf to excel"].competition == "low"


def test_dataforseo_provider_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")


    provider = _dataforseo_client(handler)
    with pytest.raises(KeywordProviderError):
        asyncio.run(provider.fetch_metrics(["pdf to excel"]))


def test_dataforseo_provider_task_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status_code": 40000, "status_message": "credits exhausted", "tasks": []}
        )


    provider = _dataforseo_client(handler)
    with pytest.raises(KeywordProviderError, match="credits exhausted"):
        asyncio.run(provider.fetch_metrics(["pdf to excel"]))


# ── Autocomplete 免费校验 ───────────────────────────────────────


def _suggest_client(handler) -> AutocompleteProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return AutocompleteProvider(interval_seconds=0, client=client)


def test_autocomplete_provider_confirms_real_search_term() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "suggestqueries.google.com"
        return httpx.Response(
            200, json=["pdf to excel", ["pdf to excel converter", "pdf to excel free"]]
        )

    provider = _suggest_client(handler)
    metrics = asyncio.run(provider.fetch_metrics(["pdf to excel"]))
    assert metrics["pdf to excel"].search_volume is None
    assert metrics["pdf to excel"].competition == "confirmed_by_suggest"


def test_autocomplete_provider_skips_unmatched_phrase() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["obscure phrase", ["something else entirely"]])

    provider = _suggest_client(handler)
    metrics = asyncio.run(provider.fetch_metrics(["obscure phrase"]))
    assert metrics == {}


def test_autocomplete_provider_uses_zh_hl_for_cjk_phrase() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["hl"] == "zh-CN"
        return httpx.Response(200, json=["银行流水转excel", ["银行流水转excel表格", "银行流水导出"]])

    provider = _suggest_client(handler)
    metrics = asyncio.run(provider.fetch_metrics(["银行流水转excel表格"]))
    assert "银行流水转excel表格" in metrics


def test_autocomplete_provider_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    provider = _suggest_client(handler)
    with pytest.raises(KeywordRateLimitedError):
        asyncio.run(provider.fetch_metrics(["pdf to excel"]))


def test_autocomplete_provider_backs_off_then_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429)
        return httpx.Response(
            200, json=["pdf to excel", ["pdf to excel converter", "pdf to excel free"]]
        )

    provider = AutocompleteProvider(
        interval_seconds=0, rate_limit_backoff_seconds=0, client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
    )
    metrics = asyncio.run(provider.fetch_metrics(["pdf to excel"]))
    assert calls["count"] == 2
    assert metrics["pdf to excel"].competition == "confirmed_by_suggest"


def test_validate_pending_rate_limit_keeps_remaining_pending(monkeypatch) -> None:
    """限流时已完成部分写回，未处理的保持待验证而不是标 error。"""

    for phrase in ("alpha tool", "beta tool", "gamma tool"):
        db.create_keyword_seed(
            {"phrase": phrase, "phrase_key": phrase, "pattern_kind": "extractor"}
        )

    class _RateLimitedProvider:
        async def fetch_metrics(self, phrases: Sequence[str]) -> dict[str, KeywordMetrics]:
            raise KeywordRateLimitedError(
                "google suggest rate limited; retry later",
                partial={"alpha tool": KeywordMetrics(competition="confirmed_by_suggest")},
            )

    monkeypatch.setattr(keyword_seeds, "resolve_keyword_provider", lambda: _RateLimitedProvider())
    result = asyncio.run(keyword_seeds.validate_pending())
    assert result.validated == 1
    assert result.skipped == 2
    assert result.errors == 0
    assert result.reason and "rate limited" in result.reason

    alpha = db.get_keyword_seed_by_key("alpha tool")
    assert alpha is not None and alpha.status == KeywordSeedStatus.VALIDATED
    for phrase in ("beta tool", "gamma tool"):
        seed = db.get_keyword_seed_by_key(phrase)
        assert seed is not None and seed.status == KeywordSeedStatus.NEW


def test_singular_variant_rules() -> None:
    from app.services.keyword_provider import _singular_variants

    # 尾词复数
    assert _singular_variants("extract text from pdfs") == ["extract text from pdf"]
    # 复数在短语中部：从后向前找可变换词
    assert _singular_variants("convert medical pdfs to excel") == [
        "convert medical pdf to excel"
    ]
    # 多个可变换位置时从后向前取至多两个
    assert _singular_variants("convert histories to files") == [
        "convert histories to file",
        "convert history to files",
    ]
    assert _singular_variants("scrape product prices") == ["scrape product price"]
    assert _singular_variants("run batch processes") == ["run batch process"]
    assert _singular_variants("ride the buses") == ["ride the bus"]
    assert _singular_variants("skip the class") == []  # ss 结尾不变换
    assert _singular_variants("银行流水转excel") == []  # 中文无数数变化
    assert _singular_variants("") == []


def test_autocomplete_provider_falls_back_to_singular_variant() -> None:
    queries = []

    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        queries.append(q)
        if q == "convert medical pdfs to excel":
            # 原话（复数）无联想命中
            return httpx.Response(200, json=[q, ["something unrelated"]])
        # 单数变体有联想命中
        return httpx.Response(
            200, json=["convert medical pdf to excel", ["convert medical pdf to excel tool"]]
        )

    provider = _suggest_client(handler)
    metrics = asyncio.run(provider.fetch_metrics(["convert medical pdfs to excel"]))
    assert queries == ["convert medical pdfs to excel", "convert medical pdf to excel"]
    assert metrics["convert medical pdfs to excel"].competition == "confirmed_by_suggest"


def test_autocomplete_provider_skips_variant_when_primary_confirms() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=["scrape data sets", ["scrape data sets tool"]])

    provider = _suggest_client(handler)
    metrics = asyncio.run(provider.fetch_metrics(["scrape data sets"]))
    assert calls["count"] == 1
    assert "scrape data sets" in metrics


def test_resolve_keyword_provider_priority(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.services import keyword_provider

    def _settings(**overrides):
        base = {
            "keyword_provider": "auto",
            "dataforseo_api_login": None,
            "dataforseo_api_password": None,
            "dataforseo_sandbox": False,
            "keyword_provider_timeout_seconds": 5.0,
            "keyword_autocomplete_interval_ms": 10,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    # auto + 无凭据 → 免费校验兜底
    monkeypatch.setattr(keyword_provider, "get_settings", lambda: _settings())
    assert isinstance(keyword_provider.resolve_keyword_provider(), AutocompleteProvider)

    # auto + 凭据齐 → DataForSEO 优先
    monkeypatch.setattr(
        keyword_provider,
        "get_settings",
        lambda: _settings(dataforseo_api_login="u", dataforseo_api_password="p"),
    )
    assert isinstance(keyword_provider.resolve_keyword_provider(), DataForSEOProvider)

    # 显式 autocomplete → 即使有 DataForSEO 凭据也走免费校验
    monkeypatch.setattr(
        keyword_provider,
        "get_settings",
        lambda: _settings(
            keyword_provider="autocomplete",
            dataforseo_api_login="u",
            dataforseo_api_password="p",
        ),
    )
    assert isinstance(keyword_provider.resolve_keyword_provider(), AutocompleteProvider)

    # none → 关闭验证
    monkeypatch.setattr(keyword_provider, "get_settings", lambda: _settings(keyword_provider="none"))
    assert keyword_provider.resolve_keyword_provider() is None


# ── API 测试 ────────────────────────────────────────────────────


def test_api_keyword_seed_flow(client: TestClient) -> None:
    _create_need(
        "Freelancer PDF Jobs",
        "Convert Medical PDFs to Excel",
        "Need someone to convert medical pdfs to excel weekly.",
    )

    extract = client.post("/api/v1/keyword-seeds/extract")
    assert extract.status_code == 201
    assert extract.json()["created"] >= 1

    listing = client.get("/api/v1/keyword-seeds/")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert body["status_breakdown"].get("new", 0) >= 1

    search = client.get("/api/v1/keyword-seeds/", params={"search": "medical"})
    assert search.status_code == 200
    assert search.json()["total"] == 1

    seed_id = body["items"][0]["id"]

    patch = client.patch(
        f"/api/v1/keyword-seeds/{seed_id}", json={"status": "shortlisted"}
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "shortlisted"

    invalid_patch = client.patch(
        f"/api/v1/keyword-seeds/{seed_id}", json={"status": "nonsense"}
    )
    assert invalid_patch.status_code == 400

    missing_patch = client.patch("/api/v1/keyword-seeds/99999", json={"status": "new"})
    assert missing_patch.status_code == 404


def test_api_validate_single_without_provider_returns_400(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(keyword_seeds, "resolve_keyword_provider", lambda: None)
    created = db.create_keyword_seed(
        {"phrase": "pdf to excel", "phrase_key": "pdf to excel", "pattern_kind": "to_converter"}
    )
    response = client.post(f"/api/v1/keyword-seeds/{created.id}/validate")
    assert response.status_code == 400
    assert "not configured" in response.json()["detail"]


def test_api_validate_pending_without_provider(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(keyword_seeds, "resolve_keyword_provider", lambda: None)
    response = client.post("/api/v1/keyword-seeds/validate-pending")
    assert response.status_code == 200
    body = response.json()
    assert body["validated"] == 0
    assert body["reason"] == "keyword provider not configured"
