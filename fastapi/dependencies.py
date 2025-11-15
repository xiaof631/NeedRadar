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
