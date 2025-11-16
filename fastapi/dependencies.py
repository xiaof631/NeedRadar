"""依赖项与参数工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Depends:
    """标记依赖项。"""

    dependency: Callable[..., Any]


def Query(default: Any = None, **_: Any) -> Any:
    """查询参数的占位实现，返回默认值。"""

    return default


@dataclass(slots=True)
class HeaderInfo:
    """表示 Header 依赖的元信息。"""

    default: Any = None
    alias: str | None = None


def Header(default: Any = None, *, alias: str | None = None, **_: Any) -> HeaderInfo:
    """Header 参数占位实现。"""

    return HeaderInfo(default=default, alias=alias)


__all__ = ["Depends", "Query", "Header", "HeaderInfo"]
