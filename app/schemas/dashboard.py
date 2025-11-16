"""仪表盘 API 的输出模型。"""

from __future__ import annotations

from app.services.dashboard import DashboardMetrics
from pydantic import BaseModel, ConfigDict


class SourcesSummaryRead(BaseModel):
    """RSS 源汇总。"""

    total: int
    active: int

    model_config = ConfigDict(from_attributes=True)


class StatusBreakdownRead(BaseModel):
    """状态分布结构。"""

    total: int
    by_status: dict[str, int]

    model_config = ConfigDict(from_attributes=True)


class FetchLogSummaryRead(BaseModel):
    """抓取日志统计结构。"""

    total: int
    failures: int

    model_config = ConfigDict(from_attributes=True)


class DashboardMetricsRead(BaseModel):
    """仪表盘核心指标。"""

    sources: SourcesSummaryRead
    raw_entries: StatusBreakdownRead
    candidate_needs: StatusBreakdownRead
    pending_sync_needs: int
    fetch_logs: FetchLogSummaryRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_metrics(cls, metrics: DashboardMetrics) -> DashboardMetricsRead:
        """根据服务层数据生成响应模型。"""

        return cls(
            sources=SourcesSummaryRead(
                total=metrics.sources.total,
                active=metrics.sources.active,
            ),
            raw_entries=StatusBreakdownRead(
                total=metrics.raw_entries.total,
                by_status=dict(metrics.raw_entries.by_status),
            ),
            candidate_needs=StatusBreakdownRead(
                total=metrics.candidate_needs.total,
                by_status=dict(metrics.candidate_needs.by_status),
            ),
            pending_sync_needs=metrics.pending_sync_needs,
            fetch_logs=FetchLogSummaryRead(
                total=metrics.fetch_logs.total,
                failures=metrics.fetch_logs.failures,
            ),
        )
