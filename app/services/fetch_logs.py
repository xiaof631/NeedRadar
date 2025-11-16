"""RSS 抓取日志相关操作。"""

from __future__ import annotations

from datetime import datetime

from app.db.storage import db
from app.models import FetchLog, FetchStatus


def list_logs(
    *,
    source_id: int | None = None,
    status: FetchStatus | None = None,
    start_fetched_at: datetime | None = None,
    end_fetched_at: datetime | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[FetchLog]]:
    """列出抓取日志并返回总数。"""

    items = db.list_fetch_logs(
        source_id=source_id,
        status=status,
        start_fetched_at=start_fetched_at,
        end_fetched_at=end_fetched_at,
        skip=skip,
        limit=limit,
    )
    total = db.count_fetch_logs(
        source_id=source_id,
        status=status,
        start_fetched_at=start_fetched_at,
        end_fetched_at=end_fetched_at,
    )
    return total, items


def iter_logs(
    *,
    source_id: int | None = None,
    status: FetchStatus | None = None,
    start_fetched_at: datetime | None = None,
    end_fetched_at: datetime | None = None,
) -> list[FetchLog]:
    """按时间倒序遍历抓取日志。"""

    return db.list_fetch_logs(
        source_id=source_id,
        status=status,
        start_fetched_at=start_fetched_at,
        end_fetched_at=end_fetched_at,
    )
