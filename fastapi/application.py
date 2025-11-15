"""极简 FastAPI 应用实现，满足测试需求。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .routing import APIRouter

Handler = Callable[..., Any]
RouteKey = tuple[str, str]


@dataclass
class Route:
    method: str
    path: str
    handler: Handler


class FastAPI:
    """FastAPI 的极简替代实现，仅支持 GET 路由。"""

    def __init__(self, title: str = "FastAPI", debug: bool = False) -> None:
        self.title = title
        self.debug = debug
        self._routes: dict[RouteKey, Route] = {}

    def get(self, path: str, summary: str | None = None) -> Callable[[Handler], Handler]:
        """注册 GET 路由。"""

        def decorator(func: Handler) -> Handler:
            self._routes[("GET", path)] = Route("GET", path, func)
            return func

        return decorator

    def include_router(self, router: APIRouter, prefix: str = "") -> None:
        """合并子路由。"""

        for method, path, handler in router.iter_routes():
            full_path = f"{prefix}{path}" if prefix else path
            self._routes[(method, full_path)] = Route(method, full_path, handler)

    def resolve(self, method: str, path: str) -> Handler | None:
        """查找指定请求的处理函数。"""

        route = self._routes.get((method.upper(), path))
        return route.handler if route else None

    async def dispatch(self, method: str, path: str, **kwargs: Any) -> Any:
        """执行请求。"""

        handler = self.resolve(method, path)
        if handler is None:
            raise LookupError(f"Route {method} {path} not found")

        if asyncio.iscoroutinefunction(handler):
            return await handler(**kwargs)
        result = handler(**kwargs)
        if isinstance(result, Awaitable):
            return await result
        return result
