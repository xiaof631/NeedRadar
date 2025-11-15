"""应用的内存数据存储实现。"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from app.models import FetchLog, FetchStatus, RawEntry, RssSource, SourceStatus


class InMemoryDatabase:
    """用于测试环境的简易数据库。"""

    def __init__(self) -> None:
        self._sources: dict[int, RssSource] = {}
        self._fetch_logs: dict[int, FetchLog] = {}
        self._raw_entries: dict[int, RawEntry] = {}
        self._raw_entry_index: dict[tuple[int, str], int] = {}
        self._source_seq = 0
        self._fetch_log_seq = 0
        self._raw_entry_seq = 0

    def reset(self) -> None:
        self._sources.clear()
        self._fetch_logs.clear()
        self._raw_entries.clear()
        self._raw_entry_index.clear()
        self._source_seq = 0
        self._fetch_log_seq = 0
        self._raw_entry_seq = 0

    # RSS 源操作
    def create_source(self, data: dict) -> RssSource:
        self._source_seq += 1
        source = RssSource(id=self._source_seq, **data)
        self._sources[source.id] = source
        return source

    def update_source(self, source_id: int, updater: Callable[[RssSource], None]) -> RssSource:
        source = self._sources[source_id]
        updater(source)
        source.touch()
        return source

    def delete_source(self, source_id: int) -> None:
        self._sources.pop(source_id, None)
        for log_id, log in list(self._fetch_logs.items()):
            if log.source_id == source_id:
                self._fetch_logs.pop(log_id)
        for entry_id, entry in list(self._raw_entries.items()):
            if entry.source_id == source_id:
                self._raw_entries.pop(entry_id)
                self._raw_entry_index.pop((entry.source_id, entry.guid), None)

    def get_source(self, source_id: int) -> RssSource | None:
        return self._sources.get(source_id)

    def list_sources(
        self,
        *,
        status: SourceStatus | None = None,
        category: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[RssSource]:
        items: Iterable[RssSource] = self._sources.values()
        if status is not None:
            items = [item for item in items if item.status == status]
        if category:
            items = [item for item in items if item.category == category]
        if search:
            keyword = search.lower()
            items = [item for item in items if keyword in item.name.lower()]
        sorted_items = sorted(items, key=lambda item: item.created_at, reverse=True)
        sliced = sorted_items[skip : skip + limit if limit is not None else None]
        return list(sliced)

    def count_sources(
        self,
        *,
        status: SourceStatus | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> int:
        return len(
            self.list_sources(status=status, category=category, search=search)
        )

    # 抓取日志操作（当前未在测试中使用）
    def add_fetch_log(
        self,
        source_id: int,
        *,
        status: FetchStatus,
        http_status: int | None = None,
        error_message: str | None = None,
    ) -> FetchLog:
        self._fetch_log_seq += 1
        log = FetchLog(
            id=self._fetch_log_seq,
            source_id=source_id,
            status=status,
            http_status=http_status,
            error_message=error_message,
        )
        self._fetch_logs[log.id] = log
        return log

    def list_fetch_logs(self, *, source_id: int | None = None) -> list[FetchLog]:
        logs: Iterable[FetchLog] = self._fetch_logs.values()
        if source_id is not None:
            logs = [log for log in logs if log.source_id == source_id]
        return sorted(logs, key=lambda item: item.fetched_at, reverse=True)

    # 原始条目操作
    def create_raw_entry(self, data: dict) -> RawEntry:
        self._raw_entry_seq += 1
        tags = tuple(data.get("tags", ()))
        entry = RawEntry(id=self._raw_entry_seq, **{**data, "tags": tags})
        self._raw_entries[entry.id] = entry
        self._raw_entry_index[(entry.source_id, entry.guid)] = entry.id
        return entry

    def get_raw_entry_by_guid(self, source_id: int, guid: str) -> RawEntry | None:
        entry_id = self._raw_entry_index.get((source_id, guid))
        if entry_id is None:
            return None
        return self._raw_entries.get(entry_id)

    def list_raw_entries(self, *, source_id: int | None = None) -> list[RawEntry]:
        entries: Iterable[RawEntry] = self._raw_entries.values()
        if source_id is not None:
            entries = [entry for entry in entries if entry.source_id == source_id]
        return sorted(entries, key=lambda item: item.published_at or item.created_at, reverse=True)


db = InMemoryDatabase()
