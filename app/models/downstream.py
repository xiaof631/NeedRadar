"""下游同步相关模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class SyncChannel(str, Enum):
    """下游同步的渠道类型。"""

    WEBHOOK = "webhook"
    MQ = "mq"
    EXPORT = "export"


@dataclass(slots=True)
class DownstreamSyncLog:
    """记录一次同步尝试的审计数据。"""

    id: int
    need_id: int
    channel: SyncChannel
    status: str
    attempt: int = 1
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    delivered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
