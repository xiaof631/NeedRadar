"""RSS 相关的领域模型。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class SourceStatus(str, Enum):
    """RSS 源的状态枚举。"""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class FetchStatus(str, Enum):
    """抓取日志的状态。"""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(slots=True)
class RssSource:
    """RSS 数据源配置。"""

    id: int
    name: str
    url: str
    category: str | None = None
    frequency: int = 3600
    status: SourceStatus = SourceStatus.ACTIVE
    last_fetched_at: datetime | None = None
    etag: str | None = None
    last_modified: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        """更新更新时间戳。"""

        self.updated_at = datetime.now(UTC)


@dataclass(slots=True)
class FetchLog:
    """RSS 抓取记录。"""

    id: int
    source_id: int
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: FetchStatus = FetchStatus.SUCCESS
    http_status: int | None = None
    error_message: str | None = None


@dataclass(slots=True)
class RawEntry:
    """RSS 抓取得到的原始条目。"""

    id: int
    source_id: int
    guid: str
    title: str
    summary: str | None = None
    content: str | None = None
    link: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    tags: Sequence[str] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)
