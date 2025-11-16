"""RSS 抓取日志相关操作。"""

from __future__ import annotations

from collections.abc import Iterable

from app.db.storage import db
from app.models import FetchLog


def list_logs(
    *,
    source_id: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[FetchLog]]:
    """列出抓取日志并返回总数。"""

    items = db.list_fetch_logs(source_id=source_id, skip=skip, limit=limit)
    total = db.count_fetch_logs(source_id=source_id)
    return total, items


def iter_logs(*, source_id: int | None = None) -> Iterable[FetchLog]:
    """按时间倒序遍历抓取日志。"""

    return db.list_fetch_logs(source_id=source_id)
