"""SQLAlchemy 的极简兼容模块。"""

from __future__ import annotations

from . import ext, orm  # noqa: F401  # 暴露子模块


def text(statement: str) -> str:
    return statement


class pool:
    class NullPool:
        pass


__all__ = ["text", "pool"]
