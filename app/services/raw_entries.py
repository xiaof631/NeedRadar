"""原始 RSS 条目相关的业务逻辑。"""

from __future__ import annotations

from typing import Any

from app.db.storage import db
from app.models import RawEntry


def create_entry(data: dict[str, Any]) -> RawEntry:
    """创建原始条目。"""

    return db.create_raw_entry(data)


def get_entry_by_guid(source_id: int, guid: str) -> RawEntry | None:
    """根据 guid 查询条目。"""

    return db.get_raw_entry_by_guid(source_id, guid)


def list_entries(*, source_id: int | None = None) -> list[RawEntry]:
    """列出原始条目，可按数据源过滤。"""

    return db.list_raw_entries(source_id=source_id)
