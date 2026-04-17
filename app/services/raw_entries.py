"""原始条目存取与工具函数。"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.db.storage import db
from app.models import RawEntry, RawEntryStatus, SourceType

_WHITESPACE_RE = re.compile(r"\s+")


class RawEntryAlreadyExistsError(Exception):
    """尝试创建重复的原始条目。"""

    def __init__(self, existing_id: int) -> None:
        super().__init__(f"raw entry #{existing_id} already exists")
        self.existing_id = existing_id


class RawEntryNotFoundError(Exception):
    """原始条目不存在。"""


def create_entry(data: dict[str, Any]) -> RawEntry:
    """创建原始条目，自动计算内容指纹并校验唯一性。"""

    payload = dict(data)
    payload.setdefault("content_hash", calculate_content_hash(payload))
    existing = db.get_raw_entry_by_guid(payload["source_id"], payload["guid"])
    if existing is not None:
        raise RawEntryAlreadyExistsError(existing.id)
    content_hash = payload.get("content_hash")
    if content_hash:
        duplicated = db.get_raw_entry_by_hash(content_hash)
        if duplicated is not None:
            raise RawEntryAlreadyExistsError(duplicated.id)
    return db.create_raw_entry(payload)


def get_entry_by_guid(source_id: int, guid: str) -> RawEntry | None:
    """根据 guid 查询条目。"""

    return db.get_raw_entry_by_guid(source_id, guid)


def get_entry_by_hash(content_hash: str) -> RawEntry | None:
    """根据内容指纹查询条目。"""

    return db.get_raw_entry_by_hash(content_hash)


def get_entry(entry_id: int) -> RawEntry:
    """根据 ID 获取原始条目，若不存在抛出异常。"""

    entry = db.get_raw_entry(entry_id)
    if entry is None:
        raise RawEntryNotFoundError
    return entry


def list_entries(
    *,
    source_id: int | None = None,
    status: RawEntryStatus | None = None,
    search: str | None = None,
    source_type: SourceType | None = None,
    start_published_at: datetime | None = None,
    end_published_at: datetime | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[RawEntry]]:
    """列出原始条目，可按数据源、状态、关键字与时间过滤。"""

    start = _normalize_datetime(start_published_at)
    end = _normalize_datetime(end_published_at)
    items = db.list_raw_entries(
        source_id=source_id,
        status=status,
        search=search,
        source_type=source_type,
        start_published_at=start,
        end_published_at=end,
        skip=skip,
        limit=limit,
    )
    total = db.count_raw_entries(
        source_id=source_id,
        status=status,
        search=search,
        source_type=source_type,
        start_published_at=start,
        end_published_at=end,
    )
    return total, items


def update_entry_status(entry_id: int, status: RawEntryStatus) -> RawEntry:
    """更新指定条目的状态。"""

    entry = db.get_raw_entry(entry_id)
    if entry is None:
        raise RawEntryNotFoundError

    def _apply(model: RawEntry) -> None:
        model.status = status

    return db.update_raw_entry(entry_id, _apply)


def bulk_update_status(entry_ids: Iterable[int], status: RawEntryStatus) -> list[RawEntry]:
    """批量更新条目状态。"""

    updated: list[RawEntry] = []
    for entry_id in entry_ids:
        updated.append(update_entry_status(entry_id, status))
    return updated


def export_entries(
    *,
    source_id: int | None = None,
    status: RawEntryStatus | None = None,
    search: str | None = None,
    source_type: SourceType | None = None,
    start_published_at: datetime | None = None,
    end_published_at: datetime | None = None,
    limit: int | None = None,
) -> list[RawEntry]:
    """根据过滤条件导出原始条目。"""

    total, items = list_entries(
        source_id=source_id,
        status=status,
        search=search,
        source_type=source_type,
        start_published_at=start_published_at,
        end_published_at=end_published_at,
        skip=0,
        limit=limit,
    )
    # list_entries 已应用 limit，total 在导出场景中无特殊用途
    return items


def calculate_content_hash(data: Mapping[str, Any]) -> str | None:
    """根据关键字段生成内容指纹，便于跨源去重。"""

    components: list[str] = []
    for field in ("link", "title", "summary", "content"):
        normalized = _normalize_text(data.get(field))
        if normalized:
            components.append(f"{field}:{normalized}")
    if not components:
        normalized_guid = _normalize_text(data.get("guid"))
        if normalized_guid:
            components.append(f"guid:{normalized_guid}")
    if not components:
        return None
    joined = "|".join(components)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    collapsed = _WHITESPACE_RE.sub(" ", text)
    lowered = collapsed.lower().strip()
    return lowered or None
