from app.models import RawEntry
from app.services.llm_client import HeuristicLLMClient


def _entry(**overrides: object) -> RawEntry:
    base = dict(
        id=1,
        source_id=1,
        guid="g-1",
        title="AI 助手为产品经理带来洞察",
        summary="产品经理经常缺乏及时反馈，这款工具能够同步 Notion 评论。",
        content=(
            "产品经理缺乏跨团队沟通渠道，" "该助手能够将飞书群内的问题整理到 Notion，"
            "也方便开发者和设计师协同。"
        ),
    )
    base.update(overrides)
    return RawEntry(**base)


def test_heuristic_llm_extracts_key_fields() -> None:
    client = HeuristicLLMClient()
    result = client.analyze_entry(_entry())

    assert "产品经理" in (result.target_users or "")
    assert result.problem_statement and "缺乏" in result.problem_statement
    assert result.value_proposition and "能够" in result.value_proposition
    assert "Notion" in (result.competition or "")
    assert 0.4 < result.confidence <= 0.95


def test_heuristic_llm_fallback_summary_and_missing_targets() -> None:
    client = HeuristicLLMClient()
    entry = _entry(
        title="效率简报",
        summary=None,
        content="这是一条没有受众信息的更新",
    )
    result = client.analyze_entry(entry)

    assert result.summary == entry.title
    assert result.target_users is None
    assert 0.4 < result.confidence <= 0.95


def test_heuristic_llm_prefers_title_when_summary_is_long_html() -> None:
    client = HeuristicLLMClient()
    entry = _entry(
        title="Calendly alternative worth switching to",
        summary="<p>" + ("Calendly is reliable but clunky for growing teams. " * 20) + "</p>",
        content=None,
    )

    result = client.analyze_entry(entry)

    assert result.summary == entry.title


def test_heuristic_llm_does_not_match_short_ascii_substrings_as_roles() -> None:
    client = HeuristicLLMClient()
    entry = _entry(
        title="Ask HN: Can anyone suggest me a SaaS product idea?",
        summary="Simple prompt with no explicit role mentions.",
        content=None,
    )

    result = client.analyze_entry(entry)

    assert result.target_users is None


def test_heuristic_llm_splits_english_sentences_for_problem_statement() -> None:
    client = HeuristicLLMClient()
    entry = _entry(
        title="Calendly alternative worth switching to",
        summary="Calendly works. The friction gets painful when teams scale. Slotably makes scheduling simpler.",
        content=None,
    )

    result = client.analyze_entry(entry)

    assert result.problem_statement == "The friction gets painful when teams scale"
