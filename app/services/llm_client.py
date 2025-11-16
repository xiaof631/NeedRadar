"""基于启发式规则的 LLM 客户端实现。"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.models import RawEntry


@dataclass(slots=True)
class StructuredNeed:
    """LLM 输出的结构化需求。"""

    summary: str
    problem_statement: str | None = None
    target_users: str | None = None
    value_proposition: str | None = None
    competition: str | None = None
    confidence: float = 0.5


class LLMClient(Protocol):
    """LLM 客户端协议。"""

    def analyze_entry(self, entry: RawEntry) -> StructuredNeed:
        """根据原始条目生成结构化需求。"""


class HeuristicLLMClient:
    """无需外部依赖的启发式 LLM 客户端。"""

    _USER_KEYWORDS: dict[str, tuple[str, ...]] = {
        "开发者": ("开发者", "程序员", "工程师"),
        "产品经理": ("产品经理", "PM"),
        "设计师": ("设计师", "UX", "UI"),
        "运营": ("运营", "市场", "营销"),
        "学生": ("学生", "高校", "大学"),
    }
    _VALUE_PATTERNS: tuple[str, ...] = ("可以", "能够", "提供", "让", "支持")
    _PROBLEM_PATTERNS: tuple[str, ...] = ("难", "痛点", "缺乏", "需要", "困扰")
    _COMPETITORS: dict[str, tuple[str, ...]] = {
        "Notion": ("Notion", "Evernote"),
        "飞书": ("飞书", "钉钉"),
        "Github": ("GitHub", "Gitlab"),
    }

    def analyze_entry(self, entry: RawEntry) -> StructuredNeed:
        text = _compose_text(entry)
        sentences = _split_sentences(text)
        summary = _build_summary(entry, sentences)
        problem = _pick_sentence(sentences, self._PROBLEM_PATTERNS)
        target_users = self._detect_target_users(text)
        value = _pick_sentence(sentences, self._VALUE_PATTERNS)
        competition = self._detect_competition(text)
        confidence = self._estimate_confidence(summary, problem, target_users, value, competition)
        return StructuredNeed(
            summary=summary,
            problem_statement=problem,
            target_users=target_users,
            value_proposition=value,
            competition=competition,
            confidence=confidence,
        )

    def _detect_target_users(self, text: str) -> str | None:
        lowered = text.lower()
        hits: list[str] = []
        for label, keywords in self._USER_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in lowered:
                    hits.append(label)
                    break
        if not hits:
            return None
        return "、".join(dict.fromkeys(hits))

    def _detect_competition(self, text: str) -> str | None:
        lowered = text.lower()
        hits: list[str] = []
        for label, keywords in self._COMPETITORS.items():
            for keyword in keywords:
                if keyword.lower() in lowered:
                    hits.append(label)
                    break
        if not hits:
            return None
        return "、".join(dict.fromkeys(hits))

    def _estimate_confidence(
        self,
        summary: str,
        problem_statement: str | None,
        target_users: str | None,
        value: str | None,
        competition: str | None,
    ) -> float:
        score = 0.35
        if summary:
            score += 0.15
        if problem_statement:
            score += 0.2
        if target_users:
            score += 0.1
        if value:
            score += 0.15
        if competition:
            score += 0.05
        return min(score, 0.95)


def _compose_text(entry: RawEntry) -> str:
    parts: list[str] = []
    for value in (entry.title, entry.summary, entry.content):
        if value:
            parts.append(value)
    return "\n".join(parts)


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r"[。！？!?\n]+", text)
    return [sentence.strip() for sentence in raw if sentence.strip()]


def _pick_sentence(sentences: Sequence[str], patterns: Sequence[str]) -> str | None:
    for sentence in sentences:
        lowered = sentence.lower()
        for pattern in patterns:
            if pattern.lower() in lowered:
                return sentence
    return None


def _build_summary(entry: RawEntry, sentences: Sequence[str]) -> str:
    if entry.summary:
        return entry.summary.strip()
    if entry.title:
        return entry.title.strip()
    if sentences:
        return sentences[0]
    return entry.content.strip() if entry.content else "未命名需求"


@lru_cache
def get_default_llm_client() -> LLMClient:
    """根据配置返回默认的 LLM 客户端实例。"""

    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider in {"heuristic", "mock"}:
        return HeuristicLLMClient()
    # 未知 provider 时兜底为启发式实现，避免调用方异常
    return HeuristicLLMClient()
