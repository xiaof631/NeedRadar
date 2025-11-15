"""SQLAlchemy ORM 兼容层。"""

from __future__ import annotations


class DeclarativeMeta(type):
    pass


class DeclarativeBase(metaclass=DeclarativeMeta):
    metadata: dict[str, object] = {}

