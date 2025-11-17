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


def _ensure_sqlite_dir(url: str) -> None:
    """确保 SQLite 数据目录存在。"""

    if url.startswith("sqlite") and ":memory:" not in url:
        path = url.split("///")[-1]
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.sync_database_url)

sync_engine: Engine = create_engine(settings.sync_database_url, future=True)
SessionLocal: sessionmaker[Session] = sessionmaker(sync_engine, expire_on_commit=False)
Base.metadata.create_all(sync_engine)

try:
    async_engine: AsyncEngine | None = create_async_engine(
        settings.database_url, future=True
    )
    AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = async_sessionmaker(
        async_engine, expire_on_commit=False
    )
except ModuleNotFoundError:  # pragma: no cover - 测试环境缺少驱动
    async_engine = None
    AsyncSessionLocal = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入的异步 Session。"""

    if AsyncSessionLocal is None:
        raise RuntimeError("Async driver is not installed; please install aiosqlite/asyncpg")

    async with AsyncSessionLocal() as session:
        yield session


__all__ = ["Base", "SessionLocal", "sync_engine", "async_engine", "get_session"]
