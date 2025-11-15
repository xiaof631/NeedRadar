"""APIRouter 的极简实现。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

Handler = Callable[..., Any]


@dataclass
class RouteInfo:
    method: str
    path: str
    handler: Handler


class APIRouter:
    """极简 APIRouter。"""

    def __init__(self) -> None:
        self._routes: list[RouteInfo] = []

    def get(self, path: str, summary: str | None = None) -> Callable[[Handler], Handler]:
        def decorator(func: Handler) -> Handler:
            self._routes.append(RouteInfo("GET", path, func))
            return func

        return decorator

    def include_router(self, router: APIRouter, prefix: str = "") -> None:
        for method, path, handler in router.iter_routes():
            full_path = f"{prefix}{path}" if prefix else path
            self._routes.append(RouteInfo(method, full_path, handler))

    def iter_routes(self) -> Iterable[tuple[str, str, Handler]]:
        for route in self._routes:
            yield route.method, route.path, route.handler
