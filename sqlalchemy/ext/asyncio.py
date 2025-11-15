"""提供 SQLAlchemy 异步接口的最小实现。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class AsyncSession:
    async def __aenter__(self) -> AsyncSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class AsyncConnection:
    async def execute(self, statement: Any) -> None:
        return None

    async def run_sync(self, func: Callable[[AsyncConnection], Any]) -> Any:
        return func(self)

    async def __aenter__(self) -> AsyncConnection:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class AsyncEngine:
    def __init__(self, url: str, echo: bool = False) -> None:
        self.url = url
        self.echo = echo

    async def connect(self) -> AsyncConnection:
        return AsyncConnection()


def create_async_engine(url: str, echo: bool = False, future: bool = True) -> AsyncEngine:
    return AsyncEngine(url=url, echo=echo)


class async_sessionmaker:
    def __init__(
        self,
        engine: AsyncEngine,
        class_: type[AsyncSession],
        expire_on_commit: bool = False,
    ) -> None:
        self.engine = engine
        self.class_ = class_
        self.expire_on_commit = expire_on_commit

    def __call__(self) -> AsyncSession:
        return self.class_()


def async_engine_from_config(
    config: dict[str, Any],
    prefix: str = "sqlalchemy.",
    future: bool = True,
) -> AsyncEngine:
    url = config.get(f"{prefix}url", "")
    return create_async_engine(url, future=future)
