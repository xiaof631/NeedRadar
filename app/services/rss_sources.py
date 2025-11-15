"""RSS 源业务逻辑。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.db.storage import db
from app.models import RssSource, SourceStatus


class RssSourceAlreadyExistsError(Exception):
    """RSS 源重复。"""


class RssSourceNotFoundError(Exception):
    """RSS 源不存在。"""


def _ensure_unique_url(url: str, exclude_id: int | None = None) -> None:
    for source in db.list_sources():
        if source.url == url and source.id != exclude_id:
            raise RssSourceAlreadyExistsError


def create_source(data: dict[str, Any]) -> RssSource:
    _ensure_unique_url(data["url"])
    return db.create_source(data)


def update_source(source_id: int, data: dict[str, Any]) -> RssSource:
    source = db.get_source(source_id)
    if source is None:
        raise RssSourceNotFoundError
    if "url" in data:
        _ensure_unique_url(data["url"], exclude_id=source_id)

    def _apply(model: RssSource) -> None:
        for key, value in data.items():
            setattr(model, key, value)

    return db.update_source(source_id, _apply)


def delete_source(source_id: int) -> None:
    if db.get_source(source_id) is None:
        raise RssSourceNotFoundError
    db.delete_source(source_id)


def get_source(source_id: int) -> RssSource:
    source = db.get_source(source_id)
    if source is None:
        raise RssSourceNotFoundError
    return source


def list_sources(
    *,
    status: SourceStatus | None = None,
    category: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[int, list[RssSource]]:
    items = db.list_sources(status=status, category=category, search=search, skip=skip, limit=limit)
    total = db.count_sources(status=status, category=category, search=search)
    return total, items


def reset_storage() -> None:
    """测试中用于清理数据。"""

    db.reset()


def mark_source_fetched(
    source_id: int,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
) -> RssSource:
    """更新数据源的抓取元数据。"""

    source = db.get_source(source_id)
    if source is None:
        raise RssSourceNotFoundError

    def _apply(model: RssSource) -> None:
        model.last_fetched_at = datetime.now(UTC)
        model.etag = etag
        model.last_modified = last_modified

    return db.update_source(source_id, _apply)
