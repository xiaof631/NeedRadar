"""筛选规则领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class FilterRule:
    """用于筛选分析的规则定义。"""

    id: int
    name: str
    description: str | None = None
    keywords: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    min_score: float = 0.0
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        """更新时间戳。"""

        self.updated_at = datetime.now(UTC)
