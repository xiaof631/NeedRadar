"""pydantic 接口的极简兼容实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FieldInfo:
    default: Any
    description: str | None = None


def Field(*, default: Any, description: str | None = None) -> FieldInfo:
    return FieldInfo(default=default, description=description)


__all__ = ["Field", "FieldInfo"]
