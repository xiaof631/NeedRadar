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


def _seed_entry() -> int:
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
