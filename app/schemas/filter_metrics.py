"""筛选流程指标的输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.filter_metrics import FilterPerformance, SourceFilterStats


class SourceFilterMetricRead(BaseModel):
    """单个 RSS 源的筛选指标。"""

    source_id: int = Field(description="数据源 ID")
    source_name: str = Field(description="数据源名称")
    total_entries: int = Field(description="该源的条目总量")
    pending_entries: int = Field(description="待处理条目数量")
    filtered_entries: int = Field(description="已标记为过滤的条目数量")
    promoted_entries: int = Field(description="已转化为候选需求的条目数量")
    ignored_entries: int = Field(description="被忽略的条目数量")
    promotion_rate: float = Field(description="该源的转化率")

    @classmethod
    def from_domain(cls, stats: SourceFilterStats) -> "SourceFilterMetricRead":
        return cls(
            source_id=stats.source_id,
            source_name=stats.source_name,
            total_entries=stats.total_entries,
            pending_entries=stats.pending_entries,
            filtered_entries=stats.filtered_entries,
            promoted_entries=stats.promoted_entries,
            ignored_entries=stats.ignored_entries,
            promotion_rate=stats.promotion_rate,
        )


class FilterPerformanceRead(BaseModel):
    """整体筛选表现指标。"""

    total_entries: int = Field(description="当前原始条目总数")
    pending_entries: int = Field(description="待处理条目总数")
    processed_entries: int = Field(description="已进入筛选流程的条目数")
    filtered_entries: int = Field(description="被规则过滤的条目数量")
    promoted_entries: int = Field(description="成功转化为候选需求的条目数量")
    ignored_entries: int = Field(description="被忽略的条目数量")
    promotion_rate: float = Field(description="整体转化率")
    average_rule_score: float | None = Field(
        default=None,
        description="候选需求的平均规则得分",
    )
    source_breakdown: list[SourceFilterMetricRead] = Field(
        default_factory=list,
        description="按数据源拆解的统计",
    )

    @classmethod
    def from_domain(cls, data: FilterPerformance) -> "FilterPerformanceRead":
        return cls(
            total_entries=data.total_entries,
            pending_entries=data.pending_entries,
            processed_entries=data.processed_entries,
            filtered_entries=data.filtered_entries,
            promoted_entries=data.promoted_entries,
            ignored_entries=data.ignored_entries,
            promotion_rate=data.promotion_rate,
            average_rule_score=data.average_rule_score,
            source_breakdown=[
                SourceFilterMetricRead.from_domain(item)
                for item in data.source_breakdown
            ],
        )
