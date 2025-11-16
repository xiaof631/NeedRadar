"""数据库会话管理（当前基于内存存储）。"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class AsyncSession:
    """兼容占位的异步 Session。"""

    async def __aenter__(self) -> "AsyncSession":  # pragma: no cover - 简化实现
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入占位符。"""

    yield AsyncSession()
