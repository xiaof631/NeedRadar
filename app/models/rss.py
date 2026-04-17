"""RSS 相关的领域模型。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class SourceStatus(str, Enum):
    """RSS 源的状态枚举。"""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class SourceType(str, Enum):
    """数据源类型。"""

    RSS = "rss"
    HACKER_NEWS = "hacker_news"
    GITHUB_ISSUES = "github_issues"
    REDDIT = "reddit"
    YOUTUBE = "youtube"
    FREELANCE_MARKETPLACE = "freelance_marketplace"


class FetchStatus(str, Enum):
    """抓取日志的状态。"""

    SUCCESS = "success"
    FAILURE = "failure"


class RawEntryStatus(str, Enum):
    """原始条目的处理状态。"""

    PENDING = "pending"
    FILTERED = "filtered"
    PROMOTED = "promoted"
    IGNORED = "ignored"


@dataclass(slots=True)
class RssSource:
    """RSS 数据源配置。"""

    id: int
    name: str
    url: str
    category: str | None = None
    frequency: int = 3600
    source_type: SourceType = SourceType.RSS
    config: dict[str, Any] = field(default_factory=dict)
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
    _on_change: Callable[[FetchLog, str, Any], None] | None = field(
        default=None, repr=False, compare=False
    )

    def __setattr__(self, name: str, value: Any) -> None:  # pragma: no cover - 简单代理
        object.__setattr__(self, name, value)
        if name == "_on_change":
            return
        callback = getattr(self, "_on_change", None)
        if callback is not None:
            callback(self, name, value)


@dataclass(slots=True)
class RawEntry:
    """RSS 抓取得到的原始条目。"""

    id: int
    source_id: int
    guid: str
    title: str
    content_hash: str | None = None
    summary: str | None = None
    content: str | None = None
    link: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    tags: Sequence[str] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: RawEntryStatus = RawEntryStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)
