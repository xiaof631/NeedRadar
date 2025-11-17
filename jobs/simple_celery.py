"""Celery API 的极简本地替身，便于在离线环境运行测试。"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


class _Config(dict):
    """兼容 Celery ``conf`` 属性的简易对象。"""

    def update(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - 兼容 dict API
        super().update(*args, **kwargs)

    def __getattr__(self, key: str) -> Any:  # pragma: no cover - 非关键路径
        try:
            return self[key]
        except KeyError as exc:  # pragma: no cover - 属性缺失
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:  # pragma: no cover - 简化设置
        self[key] = value


class _LocalTask:
    """同步执行的任务包装器。"""

    def __init__(self, func: Callable[..., Any]) -> None:
        self._func = func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)


class Celery:
    """提供 Celery 基本接口的本地实现。"""

    def __init__(self, name: str) -> None:  # pragma: no cover - 数据存储
        self.main = name
        self.conf = _Config()

    def task(self, *_, **__):
        def _decorator(func: Callable[..., Any]) -> _LocalTask:
            return _LocalTask(func)

        return _decorator

    def autodiscover_tasks(
        self,
        packages: Sequence[str] | None = None,
        *,
        related_name: str | None = None,
    ) -> None:  # pragma: no cover - 调试辅助
        # 离线测试环境中无需真正扫描模块，仅保持接口存在。
        return None
