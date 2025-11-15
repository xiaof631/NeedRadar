"""APIRouter 的极简实现。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

Handler = Callable[..., Any]


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return path


def _join_paths(prefix: str, path: str) -> str:
    base = prefix.rstrip("/") if prefix else ""
    if not path or path == "/":
        return _normalize_path(base)
    segment = path.lstrip("/")
    if base:
        return _normalize_path(f"{base}/{segment}")
    return _normalize_path(f"/{segment}")


@dataclass
class RouteInfo:
    method: str
    path: str
    handler: Handler
    status_code: int
    response_model: Any | None


class APIRouter:
    """极简 APIRouter。"""

    def __init__(self, *, prefix: str = "", tags: list[str] | None = None) -> None:
        self.prefix = prefix
        self.tags = tags or []
        self._routes: list[RouteInfo] = []

    def _add_route(self, method: str, path: str, handler: Handler, *, status_code: int, response_model: Any | None) -> None:
        full_path = _join_paths(self.prefix, path)
        self._routes.append(RouteInfo(method, full_path, handler, status_code, response_model))

    def _create_decorator(self, method: str, default_status: int) -> Callable[[Handler], Handler]:
        def decorator_factory(path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
            code = status_code if status_code is not None else default_status

            def decorator(func: Handler) -> Handler:
                self._add_route(method, path, func, status_code=code, response_model=response_model)
                return func

            return decorator

        return decorator_factory

    def get(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("GET", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def post(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("POST", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def put(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("PUT", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def delete(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("DELETE", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def include_router(self, router: APIRouter, prefix: str = "") -> None:
        for method, path, handler, status_code, response_model in router.iter_routes():
            full_path = _join_paths(prefix, path)
            self._routes.append(RouteInfo(method, full_path, handler, status_code, response_model))

    def iter_routes(self) -> Iterable[tuple[str, str, Handler, int, Any | None]]:
        for route in self._routes:
            yield route.method, route.path, route.handler, route.status_code, route.response_model
