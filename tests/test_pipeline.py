from datetime import UTC, datetime

import pytest

from app.models import RawEntryStatus, SourceStatus, SourceType
from app.services import candidate_needs, filter_rules, pipeline, raw_entries, rss_sources
from app.services.llm_client import StructuredNeed
from app.services.pipeline import CandidateAlreadyExistsError, EntryNotQualifiedError


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()


class DummyClient:
    def analyze_entry(self, entry) -> StructuredNeed:  # type: ignore[override]
        return StructuredNeed(
            summary=f"分析 {entry.title}",
            problem_statement="缺乏自动化",
            target_users="开发者",
            value_proposition="能够自动整理信息",
            competition=None,
            confidence=0.8,
        )


def _seed_entry(*, tags: list[str] | None = None) -> int:
    source = rss_sources.create_source(
        {
            "name": "Tech",
            "url": "https://example.com/tech.xml",
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-1",
            "title": "LLM 自动化助手",
            "summary": "开发者需要更快的 LLM 工作流",
            "tags": tags or [],
        }
    )
    filter_rules.create_rule(
        {
            "name": "LLM 相关",
            "keywords": ["LLM"],
            "patterns": [],
            "min_score": 0.3,
            "enabled": True,
        }
    )
    return entry.id


def _seed_entry_for_source(
    *,
    guid: str,
    title: str,
    summary: str | None,
    source_name: str,
    source_url: str,
    source_type: SourceType,
    published_at: datetime | None = None,
) -> int:
    source = rss_sources.create_source(
        {
            "name": source_name,
            "url": source_url,
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
            "source_type": source_type,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": guid,
            "title": title,
            "summary": summary,
            "published_at": published_at,
        }
    )
    return entry.id


def test_promote_entry_creates_candidate_and_updates_status() -> None:
    entry_id = _seed_entry()

    result = pipeline.promote_entry(entry_id, llm_client=DummyClient())

    assert result.candidate_need.summary.startswith("分析")
    assert raw_entries.get_entry(entry_id).status == RawEntryStatus.PROMOTED
    assert candidate_needs.get_need_by_raw_entry(entry_id) is not None
    assert result.candidate_need.rule_score == pytest.approx(result.rule_match.score)


def test_promote_entry_requires_min_score_threshold() -> None:
    entry_id = _seed_entry()

    with pytest.raises(EntryNotQualifiedError):
        pipeline.promote_entry(entry_id, min_score=1.1, llm_client=DummyClient())


def test_promote_entry_rejects_duplicate_candidates() -> None:
    entry_id = _seed_entry()
    pipeline.promote_entry(entry_id, llm_client=DummyClient())

    with pytest.raises(CandidateAlreadyExistsError):
        pipeline.promote_entry(entry_id, llm_client=DummyClient())


def test_promote_entry_boosts_scores_for_reddit_signal_tags() -> None:
    entry_id = _seed_entry(
        tags=["reddit", "reddit_comment", "complaint_signal", "alternative_request"]
    )

    result = pipeline.promote_entry(entry_id, llm_client=DummyClient())

    assert result.rule_match.score == pytest.approx(1.0)
    assert result.candidate_need.rule_score == pytest.approx(1.0)
    assert result.candidate_need.confidence == pytest.approx(0.96)


def test_promote_entry_normalizes_html_summary() -> None:
    source = rss_sources.create_source(
        {
            "name": "Feed",
            "url": "https://example.com/feed.xml",
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-html",
            "title": "HTML summary",
            "summary": "<p>manual triage &amp; repetitive onboarding tasks</p>",
        }
    )
    filter_rules.create_rule(
        {
            "name": "Pain",
            "keywords": ["manual", "onboarding"],
            "patterns": [],
            "min_score": 0.3,
            "enabled": True,
        }
    )

    result = pipeline.promote_entry(entry.id, llm_client=DummyClient())

    assert result.candidate_need.summary == "分析 HTML summary"


def test_promote_entry_truncates_long_summary_to_fit_column() -> None:
    source = rss_sources.create_source(
        {
            "name": "Long Feed",
            "url": "https://example.com/long.xml",
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-long",
            "title": "Automation request",
            "summary": "manual workflow " * 80,
        }
    )
    filter_rules.create_rule(
        {
            "name": "Automation",
            "keywords": ["manual", "workflow"],
            "patterns": [],
            "min_score": 0.3,
            "enabled": True,
        }
    )

    class LongSummaryClient:
        def analyze_entry(self, entry) -> StructuredNeed:  # type: ignore[override]
            return StructuredNeed(summary="<div>" + ("manual workflow " * 80) + "</div>")

    result = pipeline.promote_entry(entry.id, llm_client=LongSummaryClient())

    assert len(result.candidate_need.summary) == 500
    assert "<" not in result.candidate_need.summary
    assert result.candidate_need.summary.endswith("…")


def test_promote_entry_normalizes_optional_fields() -> None:
    source = rss_sources.create_source(
        {
            "name": "Issue Feed",
            "url": "https://example.com/issues.xml",
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-issue",
            "title": "Project pause stuck indefinitely",
            "summary": "project cannot pause after disk IO exhaustion",
        }
    )
    filter_rules.create_rule(
        {
            "name": "Breakage",
            "keywords": ["stuck", "cannot"],
            "patterns": [],
            "min_score": 0.3,
            "enabled": True,
        }
    )

    class NoisyClient:
        def analyze_entry(self, entry) -> StructuredNeed:  # type: ignore[override]
            return StructuredNeed(
                summary="[BUG]: Project pause stuck indefinitely",
                problem_statement="### Actual behavior Project remains stuck after disk IO exhaustion.",
                target_users="<b>开发者</b>",
                value_proposition="## Screenshots If applicable, add screenshots to help explain your problem.",
                competition="Github",
                confidence=0.7,
            )

    result = pipeline.promote_entry(entry.id, llm_client=NoisyClient())

    assert result.candidate_need.problem_statement == "Project remains stuck after disk IO exhaustion."
    assert result.candidate_need.target_users == "开发者"
    assert result.candidate_need.value_proposition is None
    assert result.candidate_need.competition is None


def test_plan_balanced_promotions_respects_source_quotas_and_skips_noise() -> None:
    filter_rules.create_rule(
        {
            "name": "Need Signals",
            "keywords": ["manual", "pain", "painful", "stuck", "offline", "error", "fail", "which"],
            "patterns": [],
            "min_score": 0.15,
            "enabled": True,
        }
    )

    skipped_show_hn = _seed_entry_for_source(
        guid="show-hn",
        title="Show HN: boringBar – a taskbar-style dock replacement for macOS",
        summary="I recently switched from a Fedora laptop to a MacBook Air.",
        source_name="Show HN",
        source_url="https://example.com/show-hn.xml",
        source_type=SourceType.HACKER_NEWS,
        published_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    skipped_monthly_thread = _seed_entry_for_source(
        guid="contributors",
        title="Ask HN: Who needs contributors? (April 2026)",
        summary="Looking for contributors to your project?",
        source_name="Ask HN",
        source_url="https://example.com/ask-hn.xml",
        source_type=SourceType.HACKER_NEWS,
        published_at=datetime(2026, 4, 11, tzinfo=UTC),
    )
    selected_hn = _seed_entry_for_source(
        guid="docker-fails",
        title="Tell HN: Docker pull fails in Spain due to football Cloudflare block",
        summary="My locally-hosted gitlab runner would fail to create pipelines.",
        source_name="Ask HN",
        source_url="https://example.com/ask-hn-2.xml",
        source_type=SourceType.HACKER_NEWS,
        published_at=datetime(2026, 4, 12, tzinfo=UTC),
    )
    selected_rss = _seed_entry_for_source(
        guid="manual-dedup",
        title="Data matching tool pain",
        summary="The dedup project that should be automated is entirely manual.",
        source_name="DEV SaaS Feed",
        source_url="https://example.com/dev.xml",
        source_type=SourceType.RSS,
        published_at=datetime(2026, 4, 13, tzinfo=UTC),
    )
    skipped_promo = _seed_entry_for_source(
        guid="promo",
        title="[推广] 稳定运营两年 AI 中转",
        summary="企业级 api 渠道服务。",
        source_name="V2EX Index",
        source_url="https://example.com/v2ex.xml",
        source_type=SourceType.RSS,
        published_at=datetime(2026, 4, 14, tzinfo=UTC),
    )

    previews = pipeline.plan_balanced_promotions(
        source_types=(SourceType.RSS, SourceType.HACKER_NEWS),
        per_source_type=1,
        min_score=0.15,
    )

    preview_ids = {preview.entry.id for preview in previews}
    assert preview_ids == {selected_rss, selected_hn}
    assert skipped_show_hn not in preview_ids
    assert skipped_monthly_thread not in preview_ids
    assert skipped_promo not in preview_ids
