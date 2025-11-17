"""下游同步的审计记录。"""

from __future__ import annotations

from typing import Any

from app.db.storage import db
from app.models import DownstreamSyncLog, SyncChannel


def log_sync_attempt(
    need_id: int,
    *,
    channel: SyncChannel,
    status: str,
    attempt: int,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DownstreamSyncLog:
    """记录一次同步尝试。"""

    return db.add_sync_log(
        need_id,
        channel=channel,
        status=status,
        attempt=attempt,
        message=message,
        metadata=metadata,
    )


def list_logs(
    *,
    need_id: int | None = None,
    channel: SyncChannel | None = None,
    limit: int = 50,
) -> list[DownstreamSyncLog]:
    """返回最新的同步日志。"""

    return db.list_sync_logs(need_id=need_id, channel=channel, limit=limit)
