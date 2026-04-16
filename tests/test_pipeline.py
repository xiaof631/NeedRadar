import pytest

from app.models import RawEntryStatus, SourceStatus
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
