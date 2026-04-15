"""数据库会话与引擎配置。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

_sync_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    """确保 SQLite 数据目录存在。"""

    if url.startswith("sqlite") and ":memory:" not in url:
        path = url.split("///")[-1]
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def get_sync_engine() -> Engine:
    """惰性初始化同步引擎，避免纯配置命令被数据库驱动阻塞。"""

    global _sync_engine
    if _sync_engine is None:
        _ensure_sqlite_dir(settings.sync_database_url)
        _sync_engine = create_engine(settings.sync_database_url, future=True)
        Base.metadata.create_all(_sync_engine)
    return _sync_engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(get_sync_engine(), expire_on_commit=False)
    return _session_factory


def SessionLocal() -> Session:
    """返回一个同步 Session。"""

    return get_session_factory()()


def get_async_engine() -> AsyncEngine:
    """惰性初始化异步引擎。"""

    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(settings.database_url, future=True)
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(), expire_on_commit=False
        )
    return _async_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入的异步 Session。"""

    try:
        session_factory = get_async_session_factory()
    except ModuleNotFoundError as exc:  # pragma: no cover - 测试环境缺少驱动
        raise RuntimeError("Async driver is not installed; please install aiosqlite/asyncpg") from exc

    async with session_factory() as session:
        yield session


__all__ = [
    "Base",
    "SessionLocal",
    "get_session",
    "get_session_factory",
    "get_sync_engine",
    "get_async_engine",
    "get_async_session_factory",
]
