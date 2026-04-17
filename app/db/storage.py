"""基于 SQLAlchemy 的数据库适配器。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.entities import (
    CandidateNeedEntity,
    CandidateNeedStatusLogEntity,
    DownstreamSyncLogEntity,
    ExportJobEntity,
    FetchLogEntity,
    FilterRuleEntity,
    RawEntryEntity,
    RssSourceEntity,
)
from app.db.session import Base, SessionLocal, get_sync_engine
from app.models import (
    CandidateNeed,
    CandidateNeedStatus,
    CandidateNeedStatusLog,
    CandidateNeedType,
    DownstreamSyncLog,
    ExportJob,
    ExportJobStatus,
    FetchLog,
    FetchStatus,
    FilterRule,
    RawEntry,
    RawEntryStatus,
    RssSource,
    SourceStatus,
    SourceType,
    SyncChannel,
)


class SQLDatabase:
    """提供与内存实现一致的接口，但存储在真实数据库中。"""

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:  # pragma: no cover - 事务回滚
            session.rollback()
            raise
        finally:
            session.close()

    def reset(self) -> None:
        # Rebuild the schema instead of only truncating rows so tests pick up
        # newly added columns on existing SQLite files.
        sync_engine = get_sync_engine()
        Base.metadata.drop_all(bind=sync_engine)
        Base.metadata.create_all(bind=sync_engine)

    # RSS 源
    def create_source(self, data: dict) -> RssSource:
        payload = {**data}
        source_type = payload.get("source_type", SourceType.RSS)
        payload["source_type"] = (
            source_type.value if isinstance(source_type, SourceType) else str(source_type)
        )
        payload["config"] = dict(payload.get("config", {}))
        status = payload.get("status", SourceStatus.ACTIVE)
        payload["status"] = status.value if isinstance(status, SourceStatus) else str(status)
        with self._session() as session:
            entity = RssSourceEntity(**payload)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_rss_source(entity)

    def update_source(self, source_id: int, updater: Callable[[RssSource], None]) -> RssSource:
        with self._session() as session:
            entity = session.get(RssSourceEntity, source_id)
            if entity is None:
                raise KeyError(source_id)
            model = _to_rss_source(entity)
            updater(model)
            _apply_source(entity, model)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_rss_source(entity)

    def delete_source(self, source_id: int) -> None:
        with self._session() as session:
            entity = session.get(RssSourceEntity, source_id)
            if entity is not None:
                session.delete(entity)

    def get_source(self, source_id: int) -> RssSource | None:
        with self._session() as session:
            entity = session.get(RssSourceEntity, source_id)
            return _to_rss_source(entity) if entity else None

    def list_sources(
        self,
        *,
        status: SourceStatus | None = None,
        source_type: SourceType | None = None,
        category: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[RssSource]:
        with self._session() as session:
            stmt = select(RssSourceEntity).order_by(RssSourceEntity.created_at.desc())
            if status is not None:
                stmt = stmt.where(RssSourceEntity.status == status.value)
            if source_type is not None:
                stmt = stmt.where(RssSourceEntity.source_type == source_type.value)
            if category:
                stmt = stmt.where(RssSourceEntity.category == category)
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(func.lower(RssSourceEntity.name).like(keyword))
            if skip:
                stmt = stmt.offset(skip)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [_to_rss_source(row) for row in rows]

    def count_sources(
        self,
        *,
        status: SourceStatus | None = None,
        source_type: SourceType | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> int:
        with self._session() as session:
            stmt = select(func.count(RssSourceEntity.id))
            if status is not None:
                stmt = stmt.where(RssSourceEntity.status == status.value)
            if source_type is not None:
                stmt = stmt.where(RssSourceEntity.source_type == source_type.value)
            if category:
                stmt = stmt.where(RssSourceEntity.category == category)
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(func.lower(RssSourceEntity.name).like(keyword))
            return session.execute(stmt).scalar_one()

    # 抓取日志
    def add_fetch_log(
        self,
        source_id: int,
        *,
        status: FetchStatus,
        http_status: int | None = None,
        error_message: str | None = None,
    ) -> FetchLog:
        with self._session() as session:
            entity = FetchLogEntity(
                source_id=source_id,
                status=status.value,
                http_status=http_status,
                error_message=error_message,
            )
            session.add(entity)
            session.flush()
            session.refresh(entity)
            log = _to_fetch_log(entity)
        self._attach_fetch_log_watcher(log)
        return log

    def _attach_fetch_log_watcher(self, log: FetchLog) -> None:
        def _callback(_: FetchLog, field: str, value: Any) -> None:
            if field not in {"fetched_at", "status", "http_status", "error_message"}:
                return
            with self._session() as session:
                entity = session.get(FetchLogEntity, log.id)
                if entity is None:
                    return
                if field == "status":
                    entity.status = (
                        value.value if isinstance(value, FetchStatus) else str(value)
                    )
                else:
                    setattr(entity, field, value)
                session.add(entity)

        log._on_change = _callback

    def list_fetch_logs(
        self,
        *,
        source_id: int | None = None,
        status: FetchStatus | None = None,
        start_fetched_at: datetime | None = None,
        end_fetched_at: datetime | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[FetchLog]:
        with self._session() as session:
            stmt = select(FetchLogEntity).order_by(FetchLogEntity.fetched_at.desc())
            if source_id is not None:
                stmt = stmt.where(FetchLogEntity.source_id == source_id)
            if status is not None:
                stmt = stmt.where(FetchLogEntity.status == status.value)
            if start_fetched_at is not None:
                stmt = stmt.where(FetchLogEntity.fetched_at >= start_fetched_at)
            if end_fetched_at is not None:
                stmt = stmt.where(FetchLogEntity.fetched_at <= end_fetched_at)
            if skip:
                stmt = stmt.offset(skip)
            if limit is not None:
                stmt = stmt.limit(limit)
            return [_to_fetch_log(row) for row in session.execute(stmt).scalars().all()]

    def count_fetch_logs(
        self,
        *,
        source_id: int | None = None,
        status: FetchStatus | None = None,
        start_fetched_at: datetime | None = None,
        end_fetched_at: datetime | None = None,
    ) -> int:
        with self._session() as session:
            stmt = select(func.count(FetchLogEntity.id))
            if source_id is not None:
                stmt = stmt.where(FetchLogEntity.source_id == source_id)
            if status is not None:
                stmt = stmt.where(FetchLogEntity.status == status.value)
            if start_fetched_at is not None:
                stmt = stmt.where(FetchLogEntity.fetched_at >= start_fetched_at)
            if end_fetched_at is not None:
                stmt = stmt.where(FetchLogEntity.fetched_at <= end_fetched_at)
            return session.execute(stmt).scalar_one()

    # 原始条目
    def create_raw_entry(self, data: dict) -> RawEntry:
        payload = {**data}
        payload["tags"] = list(payload.get("tags", ()))
        payload["status"] = RawEntryStatus(payload.get("status", RawEntryStatus.PENDING)).value
        with self._session() as session:
            entity = RawEntryEntity(**payload)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_raw_entry(entity)

    def update_raw_entry(self, entry_id: int, updater: Callable[[RawEntry], None]) -> RawEntry:
        with self._session() as session:
            entity = session.get(RawEntryEntity, entry_id)
            if entity is None:
                raise KeyError(entry_id)
            model = _to_raw_entry(entity)
            updater(model)
            _apply_raw_entry(entity, model)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_raw_entry(entity)

    def get_raw_entry(self, entry_id: int) -> RawEntry | None:
        with self._session() as session:
            entity = session.get(RawEntryEntity, entry_id)
            return _to_raw_entry(entity) if entity else None

    def get_raw_entry_by_guid(self, source_id: int, guid: str) -> RawEntry | None:
        with self._session() as session:
            stmt = select(RawEntryEntity).where(
                RawEntryEntity.source_id == source_id, RawEntryEntity.guid == guid
            )
            entity = session.execute(stmt).scalars().first()
            return _to_raw_entry(entity) if entity else None

    def get_raw_entry_by_hash(self, content_hash: str) -> RawEntry | None:
        with self._session() as session:
            stmt = select(RawEntryEntity).where(RawEntryEntity.content_hash == content_hash)
            entity = session.execute(stmt).scalars().first()
            return _to_raw_entry(entity) if entity else None

    def list_raw_entries(
        self,
        *,
        source_id: int | None = None,
        status: RawEntryStatus | None = None,
        search: str | None = None,
        start_published_at: datetime | None = None,
        end_published_at: datetime | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[RawEntry]:
        with self._session() as session:
            stmt = select(RawEntryEntity)
            if source_id is not None:
                stmt = stmt.where(RawEntryEntity.source_id == source_id)
            if status is not None:
                stmt = stmt.where(RawEntryEntity.status == status.value)
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(RawEntryEntity.title).like(keyword),
                        func.lower(RawEntryEntity.summary).like(keyword),
                        func.lower(RawEntryEntity.content).like(keyword),
                    )
                )
            if start_published_at is not None:
                stmt = stmt.where(
                    func.coalesce(RawEntryEntity.published_at, RawEntryEntity.created_at)
                    >= start_published_at
                )
            if end_published_at is not None:
                stmt = stmt.where(
                    func.coalesce(RawEntryEntity.published_at, RawEntryEntity.created_at)
                    <= end_published_at
                )
            stmt = stmt.order_by(
                func.coalesce(RawEntryEntity.published_at, RawEntryEntity.created_at).desc()
            )
            if skip:
                stmt = stmt.offset(skip)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [_to_raw_entry(row) for row in rows]

    def count_raw_entries(
        self,
        *,
        source_id: int | None = None,
        status: RawEntryStatus | None = None,
        search: str | None = None,
        start_published_at: datetime | None = None,
        end_published_at: datetime | None = None,
    ) -> int:
        with self._session() as session:
            stmt = select(func.count(RawEntryEntity.id))
            if source_id is not None:
                stmt = stmt.where(RawEntryEntity.source_id == source_id)
            if status is not None:
                stmt = stmt.where(RawEntryEntity.status == status.value)
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(RawEntryEntity.title).like(keyword),
                        func.lower(RawEntryEntity.summary).like(keyword),
                        func.lower(RawEntryEntity.content).like(keyword),
                    )
                )
            if start_published_at is not None:
                stmt = stmt.where(
                    func.coalesce(RawEntryEntity.published_at, RawEntryEntity.created_at)
                    >= start_published_at
                )
            if end_published_at is not None:
                stmt = stmt.where(
                    func.coalesce(RawEntryEntity.published_at, RawEntryEntity.created_at)
                    <= end_published_at
                )
            return session.execute(stmt).scalar_one()

    # 候选需求
    def create_candidate_need(self, data: dict) -> CandidateNeed:
        payload = {**data}
        payload["status"] = CandidateNeedStatus(
            payload.get("status", CandidateNeedStatus.PENDING_REVIEW)
        ).value
        candidate_type = payload.get("candidate_type")
        if candidate_type is not None:
            payload["candidate_type"] = (
                candidate_type.value
                if isinstance(candidate_type, CandidateNeedType)
                else str(candidate_type)
            )
        with self._session() as session:
            entity = CandidateNeedEntity(**payload)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_candidate_need(entity)

    def update_candidate_need(
        self, need_id: int, updater: Callable[[CandidateNeed], None]
    ) -> CandidateNeed:
        with self._session() as session:
            entity = session.get(CandidateNeedEntity, need_id)
            if entity is None:
                raise KeyError(need_id)
            model = _to_candidate_need(entity)
            updater(model)
            _apply_candidate_need(entity, model)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_candidate_need(entity)

    def delete_candidate_need(self, need_id: int) -> None:
        with self._session() as session:
            entity = session.get(CandidateNeedEntity, need_id)
            if entity is not None:
                session.delete(entity)

    def get_candidate_need(self, need_id: int) -> CandidateNeed | None:
        with self._session() as session:
            entity = session.get(CandidateNeedEntity, need_id)
            return _to_candidate_need(entity) if entity else None

    def get_candidate_need_by_raw_entry(self, raw_entry_id: int) -> CandidateNeed | None:
        with self._session() as session:
            stmt = select(CandidateNeedEntity).where(
                CandidateNeedEntity.raw_entry_id == raw_entry_id
            )
            entity = session.execute(stmt).scalars().first()
            return _to_candidate_need(entity) if entity else None

    def list_candidate_needs(
        self,
        *,
        statuses: Iterable[CandidateNeedStatus] | None = None,
        search: str | None = None,
        raw_entry_id: int | None = None,
        source_type: SourceType | None = None,
        candidate_type: CandidateNeedType | None = None,
        min_review_readiness: float | None = None,
        review_ready_only: bool | None = None,
        synced: bool | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[CandidateNeed]:
        with self._session() as session:
            stmt = select(CandidateNeedEntity).order_by(CandidateNeedEntity.created_at.desc())
            if source_type is not None:
                stmt = (
                    stmt.join(RawEntryEntity, CandidateNeedEntity.raw_entry_id == RawEntryEntity.id)
                    .join(RssSourceEntity, RawEntryEntity.source_id == RssSourceEntity.id)
                    .where(RssSourceEntity.source_type == source_type.value)
                )
            if statuses:
                stmt = stmt.where(
                    CandidateNeedEntity.status.in_([status.value for status in statuses])
                )
            if candidate_type is not None:
                stmt = stmt.where(CandidateNeedEntity.candidate_type == candidate_type.value)
            if min_review_readiness is not None:
                stmt = stmt.where(CandidateNeedEntity.review_readiness >= min_review_readiness)
            if review_ready_only:
                stmt = stmt.where(CandidateNeedEntity.review_readiness >= 0.55).where(
                    CandidateNeedEntity.candidate_type != CandidateNeedType.BUG_REPORT.value
                )
            if raw_entry_id is not None:
                stmt = stmt.where(CandidateNeedEntity.raw_entry_id == raw_entry_id)
            if synced is not None:
                if synced:
                    stmt = stmt.where(CandidateNeedEntity.synced_at.is_not(None))
                else:
                    stmt = stmt.where(CandidateNeedEntity.synced_at.is_(None))
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(CandidateNeedEntity.summary).like(keyword),
                        func.lower(CandidateNeedEntity.problem_statement).like(keyword),
                        func.lower(CandidateNeedEntity.target_users).like(keyword),
                        func.lower(CandidateNeedEntity.value_proposition).like(keyword),
                        func.lower(CandidateNeedEntity.competition).like(keyword),
                        func.lower(CandidateNeedEntity.notes).like(keyword),
                    )
                )
            if skip:
                stmt = stmt.offset(skip)
            if limit is not None:
                stmt = stmt.limit(limit)
            return [_to_candidate_need(row) for row in session.execute(stmt).scalars().all()]

    def count_candidate_needs(
        self,
        *,
        statuses: Iterable[CandidateNeedStatus] | None = None,
        search: str | None = None,
        raw_entry_id: int | None = None,
        source_type: SourceType | None = None,
        candidate_type: CandidateNeedType | None = None,
        min_review_readiness: float | None = None,
        review_ready_only: bool | None = None,
        synced: bool | None = None,
    ) -> int:
        with self._session() as session:
            stmt = select(func.count(CandidateNeedEntity.id))
            if source_type is not None:
                stmt = (
                    stmt.select_from(CandidateNeedEntity)
                    .join(RawEntryEntity, CandidateNeedEntity.raw_entry_id == RawEntryEntity.id)
                    .join(RssSourceEntity, RawEntryEntity.source_id == RssSourceEntity.id)
                    .where(RssSourceEntity.source_type == source_type.value)
                )
            if statuses:
                stmt = stmt.where(
                    CandidateNeedEntity.status.in_([status.value for status in statuses])
                )
            if candidate_type is not None:
                stmt = stmt.where(CandidateNeedEntity.candidate_type == candidate_type.value)
            if min_review_readiness is not None:
                stmt = stmt.where(CandidateNeedEntity.review_readiness >= min_review_readiness)
            if review_ready_only:
                stmt = stmt.where(CandidateNeedEntity.review_readiness >= 0.55).where(
                    CandidateNeedEntity.candidate_type != CandidateNeedType.BUG_REPORT.value
                )
            if raw_entry_id is not None:
                stmt = stmt.where(CandidateNeedEntity.raw_entry_id == raw_entry_id)
            if synced is not None:
                if synced:
                    stmt = stmt.where(CandidateNeedEntity.synced_at.is_not(None))
                else:
                    stmt = stmt.where(CandidateNeedEntity.synced_at.is_(None))
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(CandidateNeedEntity.summary).like(keyword),
                        func.lower(CandidateNeedEntity.problem_statement).like(keyword),
                        func.lower(CandidateNeedEntity.target_users).like(keyword),
                        func.lower(CandidateNeedEntity.value_proposition).like(keyword),
                        func.lower(CandidateNeedEntity.competition).like(keyword),
                        func.lower(CandidateNeedEntity.notes).like(keyword),
                    )
                )
            return session.execute(stmt).scalar_one()

    def list_candidate_need_logs(self, need_id: int) -> list[CandidateNeedStatusLog]:
        with self._session() as session:
            stmt = (
                select(CandidateNeedStatusLogEntity)
                .where(CandidateNeedStatusLogEntity.need_id == need_id)
                .order_by(CandidateNeedStatusLogEntity.changed_at.asc())
            )
            return [
                _to_candidate_need_log(row)
                for row in session.execute(stmt).scalars().all()
            ]

    def add_candidate_need_log(
        self,
        need_id: int,
        *,
        from_status: CandidateNeedStatus | None,
        to_status: CandidateNeedStatus,
        note: str | None = None,
    ) -> CandidateNeedStatusLog:
        with self._session() as session:
            entity = CandidateNeedStatusLogEntity(
                need_id=need_id,
                from_status=from_status.value if from_status else None,
                to_status=to_status.value,
                note=note,
            )
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_candidate_need_log(entity)

    def add_sync_log(
        self,
        need_id: int,
        *,
        channel: SyncChannel,
        status: str,
        attempt: int,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DownstreamSyncLog:
        with self._session() as session:
            entity = DownstreamSyncLogEntity(
                need_id=need_id,
                channel=channel.value,
                status=status,
                attempt=attempt,
                message=message,
                details=metadata or {},
            )
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_sync_log(entity)

    def list_sync_logs(
        self,
        *,
        need_id: int | None = None,
        channel: SyncChannel | None = None,
        limit: int = 50,
    ) -> list[DownstreamSyncLog]:
        with self._session() as session:
            stmt = select(DownstreamSyncLogEntity).order_by(
                DownstreamSyncLogEntity.delivered_at.desc()
            )
            if need_id is not None:
                stmt = stmt.where(DownstreamSyncLogEntity.need_id == need_id)
            if channel is not None:
                stmt = stmt.where(DownstreamSyncLogEntity.channel == channel.value)
            if limit:
                stmt = stmt.limit(limit)
            return [_to_sync_log(row) for row in session.execute(stmt).scalars().all()]

    # 导出任务
    def create_export_job(self, data: dict) -> ExportJob:
        payload = {**data}
        status = payload.get("status", ExportJobStatus.PENDING)
        if isinstance(status, ExportJobStatus):
            payload["status"] = status.value
        payload["filters"] = dict(payload.get("filters", {}) or {})
        with self._session() as session:
            entity = ExportJobEntity(**payload)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_export_job(entity)

    def update_export_job(
        self, job_id: int, updater: Callable[[ExportJob], None]
    ) -> ExportJob:
        with self._session() as session:
            entity = session.get(ExportJobEntity, job_id)
            if entity is None:
                raise KeyError(job_id)
            model = _to_export_job(entity)
            updater(model)
            _apply_export_job(entity, model)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_export_job(entity)

    def get_export_job(self, job_id: int) -> ExportJob | None:
        with self._session() as session:
            entity = session.get(ExportJobEntity, job_id)
            return _to_export_job(entity) if entity else None

    def list_export_jobs(
        self,
        *,
        job_type: str | None = None,
        status: ExportJobStatus | None = None,
        limit: int | None = None,
    ) -> list[ExportJob]:
        with self._session() as session:
            stmt = select(ExportJobEntity).order_by(ExportJobEntity.created_at.desc())
            if job_type is not None:
                stmt = stmt.where(ExportJobEntity.job_type == job_type)
            if status is not None:
                stmt = stmt.where(ExportJobEntity.status == status.value)
            if limit is not None:
                stmt = stmt.limit(limit)
            return [_to_export_job(row) for row in session.execute(stmt).scalars().all()]

    # 筛选规则
    def create_filter_rule(self, data: dict) -> FilterRule:
        payload = {**data}
        payload["keywords"] = list(payload.get("keywords", ()))
        payload["patterns"] = list(payload.get("patterns", ()))
        with self._session() as session:
            entity = FilterRuleEntity(**payload)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_filter_rule(entity)

    def update_filter_rule(
        self, rule_id: int, updater: Callable[[FilterRule], None]
    ) -> FilterRule:
        with self._session() as session:
            entity = session.get(FilterRuleEntity, rule_id)
            if entity is None:
                raise KeyError(rule_id)
            model = _to_filter_rule(entity)
            updater(model)
            _apply_filter_rule(entity, model)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _to_filter_rule(entity)

    def delete_filter_rule(self, rule_id: int) -> None:
        with self._session() as session:
            entity = session.get(FilterRuleEntity, rule_id)
            if entity is not None:
                session.delete(entity)

    def get_filter_rule(self, rule_id: int) -> FilterRule | None:
        with self._session() as session:
            entity = session.get(FilterRuleEntity, rule_id)
            return _to_filter_rule(entity) if entity else None

    def list_filter_rules(
        self,
        *,
        enabled: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[FilterRule]:
        with self._session() as session:
            stmt = select(FilterRuleEntity).order_by(FilterRuleEntity.created_at.desc())
            if enabled is not None:
                stmt = stmt.where(FilterRuleEntity.enabled.is_(enabled))
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(FilterRuleEntity.name).like(keyword),
                        func.lower(FilterRuleEntity.description).like(keyword),
                    )
                )
            if skip:
                stmt = stmt.offset(skip)
            if limit is not None:
                stmt = stmt.limit(limit)
            return [_to_filter_rule(row) for row in session.execute(stmt).scalars().all()]

    def count_filter_rules(
        self,
        *,
        enabled: bool | None = None,
        search: str | None = None,
    ) -> int:
        with self._session() as session:
            stmt = select(func.count(FilterRuleEntity.id))
            if enabled is not None:
                stmt = stmt.where(FilterRuleEntity.enabled.is_(enabled))
            if search:
                keyword = f"%{search.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(FilterRuleEntity.name).like(keyword),
                        func.lower(FilterRuleEntity.description).like(keyword),
                    )
                )
            return session.execute(stmt).scalar_one()


def _to_rss_source(entity: RssSourceEntity) -> RssSource:
    return RssSource(
        id=entity.id,
        name=entity.name,
        url=entity.url,
        category=entity.category,
        frequency=entity.frequency,
        source_type=SourceType(entity.source_type),
        config=dict(entity.config or {}),
        status=SourceStatus(entity.status),
        last_fetched_at=entity.last_fetched_at,
        etag=entity.etag,
        last_modified=entity.last_modified,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _apply_source(entity: RssSourceEntity, model: RssSource) -> None:
    entity.name = model.name
    entity.url = model.url
    entity.category = model.category
    entity.frequency = model.frequency
    if isinstance(model.source_type, SourceType):
        entity.source_type = model.source_type.value
    else:
        entity.source_type = str(model.source_type)
    entity.config = dict(model.config)
    if isinstance(model.status, SourceStatus):
        entity.status = model.status.value
    else:
        entity.status = str(model.status)
    entity.last_fetched_at = model.last_fetched_at
    entity.etag = model.etag
    entity.last_modified = model.last_modified
    entity.updated_at = datetime.now(UTC)


def _to_fetch_log(entity: FetchLogEntity) -> FetchLog:
    return FetchLog(
        id=entity.id,
        source_id=entity.source_id,
        fetched_at=entity.fetched_at,
        status=FetchStatus(entity.status),
        http_status=entity.http_status,
        error_message=entity.error_message,
    )


def _to_raw_entry(entity: RawEntryEntity) -> RawEntry:
    return RawEntry(
        id=entity.id,
        source_id=entity.source_id,
        guid=entity.guid,
        title=entity.title,
        content_hash=entity.content_hash,
        summary=entity.summary,
        content=entity.content,
        link=entity.link,
        published_at=entity.published_at,
        author=entity.author,
        tags=tuple(entity.tags or []),
        status=RawEntryStatus(entity.status),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _apply_raw_entry(entity: RawEntryEntity, model: RawEntry) -> None:
    entity.source_id = model.source_id
    entity.guid = model.guid
    entity.title = model.title
    entity.content_hash = model.content_hash
    entity.summary = model.summary
    entity.content = model.content
    entity.link = model.link
    entity.published_at = model.published_at
    entity.author = model.author
    entity.tags = list(model.tags)
    entity.status = model.status.value
    entity.updated_at = datetime.now(UTC)


def _to_candidate_need(entity: CandidateNeedEntity) -> CandidateNeed:
    return CandidateNeed(
        id=entity.id,
        raw_entry_id=entity.raw_entry_id,
        summary=entity.summary,
        problem_statement=entity.problem_statement,
        target_users=entity.target_users,
        value_proposition=entity.value_proposition,
        competition=entity.competition,
        candidate_type=CandidateNeedType(entity.candidate_type)
        if entity.candidate_type
        else None,
        review_readiness=entity.review_readiness,
        notes=entity.notes,
        status=CandidateNeedStatus(entity.status),
        confidence=entity.confidence,
        rule_score=entity.rule_score,
        synced_at=entity.synced_at,
        sync_error=entity.sync_error,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _apply_candidate_need(entity: CandidateNeedEntity, model: CandidateNeed) -> None:
    entity.raw_entry_id = model.raw_entry_id
    entity.summary = model.summary
    entity.problem_statement = model.problem_statement
    entity.target_users = model.target_users
    entity.value_proposition = model.value_proposition
    entity.competition = model.competition
    entity.candidate_type = model.candidate_type.value if model.candidate_type else None
    entity.review_readiness = model.review_readiness
    entity.notes = model.notes
    entity.status = model.status.value
    entity.confidence = model.confidence
    entity.rule_score = model.rule_score
    entity.synced_at = model.synced_at
    entity.sync_error = model.sync_error
    entity.updated_at = datetime.now(UTC)


def _to_candidate_need_log(entity: CandidateNeedStatusLogEntity) -> CandidateNeedStatusLog:
    return CandidateNeedStatusLog(
        id=entity.id,
        need_id=entity.need_id,
        from_status=CandidateNeedStatus(entity.from_status)
        if entity.from_status
        else None,
        to_status=CandidateNeedStatus(entity.to_status),
        note=entity.note,
        changed_at=entity.changed_at,
    )


def _to_sync_log(entity: DownstreamSyncLogEntity) -> DownstreamSyncLog:
    return DownstreamSyncLog(
        id=entity.id,
        need_id=entity.need_id,
        channel=SyncChannel(entity.channel),
        status=entity.status,
        attempt=entity.attempt,
        message=entity.message,
        metadata=dict(entity.details or {}),
        delivered_at=entity.delivered_at,
    )


def _to_export_job(entity: ExportJobEntity) -> ExportJob:
    return ExportJob(
        id=entity.id,
        job_type=entity.job_type,
        format=entity.format,
        status=ExportJobStatus(entity.status),
        filters=dict(entity.filters or {}),
        record_count=entity.record_count,
        file_path=entity.file_path,
        error_message=entity.error_message,
        attempt_count=entity.attempt_count,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        started_at=entity.started_at,
        finished_at=entity.finished_at,
    )


def _apply_export_job(entity: ExportJobEntity, model: ExportJob) -> None:
    entity.job_type = model.job_type
    entity.format = model.format
    entity.status = model.status.value
    entity.filters = dict(model.filters)
    entity.record_count = model.record_count
    entity.file_path = model.file_path
    entity.error_message = model.error_message
    entity.attempt_count = model.attempt_count
    entity.started_at = model.started_at
    entity.finished_at = model.finished_at
    entity.updated_at = datetime.now(UTC)


def _to_filter_rule(entity: FilterRuleEntity) -> FilterRule:
    return FilterRule(
        id=entity.id,
        name=entity.name,
        description=entity.description,
        keywords=tuple(entity.keywords or []),
        patterns=tuple(entity.patterns or []),
        min_score=entity.min_score,
        weight=entity.weight,
        enabled=entity.enabled,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _apply_filter_rule(entity: FilterRuleEntity, model: FilterRule) -> None:
    entity.name = model.name
    entity.description = model.description
    entity.keywords = list(model.keywords)
    entity.patterns = list(model.patterns)
    entity.min_score = model.min_score
    entity.weight = model.weight
    entity.enabled = model.enabled
    entity.updated_at = datetime.now(UTC)


db = SQLDatabase()
