"""SQLAlchemy ORM 实体定义。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models import (
    CandidateNeedStatus,
    CandidateNeedType,
    ExportJobStatus,
    FetchStatus,
    RawEntryStatus,
    SourceStatus,
    SourceType,
    SyncChannel,
)


class TimestampMixin:
    """提供 created/updated 字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=func.now(),
        nullable=False,
    )


class RssSourceEntity(TimestampMixin, Base):
    __tablename__ = "rss_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[int] = mapped_column(Integer, default=3600)
    source_type: Mapped[str] = mapped_column(String(32), default=SourceType.RSS.value)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=SourceStatus.ACTIVE.value)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str | None] = mapped_column(String(200))
    last_modified: Mapped[str | None] = mapped_column(String(200))

    fetch_logs: Mapped[list[FetchLogEntity]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    raw_entries: Mapped[list[RawEntryEntity]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class FetchLogEntity(Base):
    __tablename__ = "fetch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rss_sources.id", ondelete="CASCADE"))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default=FetchStatus.SUCCESS.value)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    source: Mapped[RssSourceEntity] = relationship(back_populates="fetch_logs")


class RawEntryEntity(TimestampMixin, Base):
    __tablename__ = "raw_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rss_sources.id", ondelete="CASCADE"))
    guid: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(128), unique=True)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author: Mapped[str | None] = mapped_column(String(200))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default=RawEntryStatus.PENDING.value)

    source: Mapped[RssSourceEntity] = relationship(back_populates="raw_entries")

    __table_args__ = (
        Index("ix_raw_entries_source_guid", "source_id", "guid", unique=True),
    )


class FilterRuleEntity(TimestampMixin, Base):
    __tablename__ = "filter_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    patterns: Mapped[list[str]] = mapped_column(JSON, default=list)
    min_score: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class CandidateNeedEntity(TimestampMixin, Base):
    __tablename__ = "candidate_needs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_entry_id: Mapped[int] = mapped_column(
        ForeignKey("raw_entries.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(500))
    problem_statement: Mapped[str | None] = mapped_column(Text)
    target_users: Mapped[str | None] = mapped_column(Text)
    value_proposition: Mapped[str | None] = mapped_column(Text)
    competition: Mapped[str | None] = mapped_column(Text)
    candidate_type: Mapped[str | None] = mapped_column(
        String(32), default=CandidateNeedType.MARKET_SIGNAL.value
    )
    review_readiness: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), default=CandidateNeedStatus.PENDING_REVIEW.value
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    rule_score: Mapped[float | None] = mapped_column(Float)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[str | None] = mapped_column(Text)

    logs: Mapped[list[CandidateNeedStatusLogEntity]] = relationship(
        back_populates="need", cascade="all, delete-orphan"
    )


class CandidateNeedStatusLogEntity(Base):
    __tablename__ = "candidate_need_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("candidate_needs.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    need: Mapped[CandidateNeedEntity] = relationship(back_populates="logs")


class DownstreamSyncLogEntity(Base):
    __tablename__ = "downstream_sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("candidate_needs.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(32), default=SyncChannel.WEBHOOK.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    need: Mapped[CandidateNeedEntity] = relationship()


class ExportJobEntity(TimestampMixin, Base):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ExportJobStatus.PENDING.value)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    record_count: Mapped[int | None] = mapped_column(Integer)
    file_path: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "RssSourceEntity",
    "FetchLogEntity",
    "RawEntryEntity",
    "FilterRuleEntity",
    "CandidateNeedEntity",
    "CandidateNeedStatusLogEntity",
    "DownstreamSyncLogEntity",
    "ExportJobEntity",
]
