"""下游同步通道相关的聚合指标。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.db.storage import db
from app.models import DownstreamSyncLog, SyncChannel


@dataclass(slots=True)
class SyncChannelStats:
    """记录单个下游通道的统计数据。"""

    channel: SyncChannel
    total_attempts: int = 0
    success: int = 0
    failed: int = 0
    last_attempt_at: datetime | None = None
    last_error: str | None = None

    @property
    def pending(self) -> int:
        return max(0, self.total_attempts - self.success - self.failed)

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.success / self.total_attempts


def summarize_recent_sync_logs(*, limit: int = 200) -> list[SyncChannelStats]:
    """基于最近的审计日志聚合每个通道的表现。"""

    if limit <= 0:
        return []

    stats: dict[SyncChannel, SyncChannelStats] = {
        channel: SyncChannelStats(channel=channel) for channel in SyncChannel
    }
    logs = db.list_sync_logs(limit=limit)
    for log in logs:
        channel_stats = stats.setdefault(log.channel, SyncChannelStats(channel=log.channel))
        channel_stats.total_attempts += 1
        _apply_status(channel_stats, log)

    # 依照枚举顺序返回，方便前端稳定展示
    return [stats[channel] for channel in SyncChannel]


def _apply_status(stats: SyncChannelStats, log: DownstreamSyncLog) -> None:
    if log.status == "success":
        stats.success += 1
    elif log.status == "failed":
        stats.failed += 1
        stats.last_error = log.message
    if stats.last_attempt_at is None or log.delivered_at > stats.last_attempt_at:
        stats.last_attempt_at = log.delivered_at
        if log.status == "failed":
            stats.last_error = log.message
