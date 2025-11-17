from __future__ import annotations

import asyncio
import inspect
import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Annotated, get_args, get_origin

from pydantic import BaseModel

from .dependencies import Depends, HeaderInfo
from .responses import Response as PlainResponse
from .routing import APIRouter, _normalize_path, _join_paths

Handler = Callable[..., Any]
RouteKey = tuple[str, str]


@dataclass
class Route:
    method: str
    path: str
    handler: Handler
    status_code: int
    response_model: Any | None
    dependencies: tuple[Depends, ...]


class FastAPI:
    """FastAPI 的极简替代实现，支持基本的同步/异步处理。"""

    def __init__(self, title: str = "FastAPI", debug: bool = False) -> None:
        self.title = title
        self.debug = debug
        self._routes: dict[RouteKey, Route] = {}
        self._routes_list: list[Route] = []
        self._startup_handlers: list[Callable[[], Awaitable[None] | None]] = []
        self._shutdown_handlers: list[Callable[[], Awaitable[None] | None]] = []

    def on_event(self, event: str) -> Callable[[Handler], Handler]:
        if event not in {"startup", "shutdown"}:
            raise ValueError(f"Unsupported event type: {event}")

        def decorator(func: Handler) -> Handler:
            if event == "startup":
                self._startup_handlers.append(func)
            else:
                self._shutdown_handlers.append(func)
            return func

        return decorator

    def trigger_startup(self) -> None:
        asyncio.run(self._run_event_handlers(self._startup_handlers))

    def trigger_shutdown(self) -> None:
        asyncio.run(self._run_event_handlers(self._shutdown_handlers, reverse=True))

    async def _run_event_handlers(self, handlers: list[Callable[[], Awaitable[None] | None]], *, reverse: bool = False) -> None:
        sequence = reversed(handlers) if reverse else handlers
        for handler in sequence:
            result = handler()
            if asyncio.iscoroutine(result):
                await result
            elif isinstance(result, Awaitable):
                await result

    def _create_route(
        self,
        method: str,
        path: str,
        handler: Handler,
        *,
        status_code: int,
        response_model: Any | None,
        dependencies: tuple[Depends, ...] | None = None,
    ) -> None:
        normalized = _normalize_path(path)
        method_key = method.upper()
        route = Route(
            method_key,
            normalized,
            handler,
            status_code,
            response_model,
            tuple(dependencies or ()),
        )
        self._routes[(method_key, normalized)] = route
        self._routes_list.append(route)

    def _create_decorator(self, method: str, default_status: int) -> Callable[[Handler], Handler]:
        def decorator(path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
            code = status_code if status_code is not None else default_status

            def wrapper(func: Handler) -> Handler:
                self._create_route(
                    method,
                    path,
                    func,
                    status_code=code,
                    response_model=response_model,
                )
                return func

            return wrapper

        return decorator

    def get(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("GET", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def post(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("POST", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def put(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("PUT", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def delete(self, path: str, *, status_code: int | None = None, response_model: Any | None = None, summary: str | None = None) -> Callable[[Handler], Handler]:
        return self._create_decorator("DELETE", 200)(path, status_code=status_code, response_model=response_model, summary=summary)

    def include_router(self, router: APIRouter, prefix: str = "") -> None:
        for method, path, handler, status_code, response_model, dependencies in router.iter_routes():
            full_path = _join_paths(prefix, path) if prefix else path
            self._create_route(
                method,
                full_path,
                handler,
                status_code=status_code,
                response_model=response_model,
                dependencies=dependencies,
            )

    def resolve(self, method: str, path: str) -> tuple[Route | None, dict[str, str]]:
        """查找指定请求的处理函数。"""

        normalized = _normalize_path(path)
        direct = self._routes.get((method.upper(), normalized))
        if direct is not None:
            return direct, {}
        for candidate in self._routes_list:
            if candidate.method != method.upper():
                continue
            params = self._match_path(candidate.path, normalized)
            if params is not None:
                return candidate, params
        return None, {}

    async def dispatch(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """执行请求。"""

        route, path_params = self.resolve(method, path)
        if route is None:
            raise LookupError(f"Route {method} {path} not found")

        closers: list[Callable[[], Awaitable[None] | None]] = []
        try:
            kwargs = await self._build_kwargs(
                route.handler,
                params=params or {},
                json=json,
                path_params=path_params,
                headers=headers or {},
                closers=closers,
            )
            await self._run_route_dependencies(
                route,
                params=params or {},
                headers=headers or {},
                closers=closers,
            )
            result = await self._call_handler(route.handler, **kwargs)
            payload = self._render_response(result, route.response_model)
            return route.status_code, payload
        finally:
            await self._close_dependencies(closers)

    def _match_path(self, template: str, actual: str) -> dict[str, str] | None:
        if template == actual:
            return {}
        template_parts = [part for part in template.strip('/').split('/') if part]
        actual_parts = [part for part in actual.strip('/').split('/') if part]
        if len(template_parts) != len(actual_parts):
            return None
        params: dict[str, str] = {}
        for expected, given in zip(template_parts, actual_parts):
            if expected.startswith('{') and expected.endswith('}'):
                params[expected[1:-1]] = given
            elif expected == given:
                continue
            else:
                return None
        return params

    async def _call_handler(self, handler: Handler, **kwargs: Any) -> Any:
        result = handler(**kwargs)
        if asyncio.iscoroutine(result):
            return await result
        if isinstance(result, Awaitable):
            return await result
        return result

    async def _close_dependencies(self, closers: list[Callable[[], Awaitable[None] | None]]) -> None:
        for closer in reversed(closers):
            outcome = closer()
            if asyncio.iscoroutine(outcome):
                await outcome

    async def _run_route_dependencies(
        self,
        route: Route,
        *,
        params: dict[str, Any],
        headers: dict[str, Any],
        closers: list[Callable[[], Awaitable[None] | None]],
    ) -> None:
        for dependency in route.dependencies:
            await self._resolve_dependency(
                dependency.dependency,
                params=params,
                headers=headers,
                closers=closers,
            )

    async def _build_kwargs(
        self,
        handler: Handler,
        *,
        params: dict[str, Any],
        json: Any,
        path_params: dict[str, str],
        headers: dict[str, Any],
        closers: list[Callable[[], Awaitable[None] | None]],
    ) -> dict[str, Any]:
        signature = inspect.signature(handler)
        bound: dict[str, Any] = {}
        body_consumed = False
        for name, parameter in signature.parameters.items():
            default = parameter.default
            annotation = parameter.annotation
            if isinstance(annotation, str):
                annotation = eval(annotation, handler.__globals__)
            origin = get_origin(annotation)
            metadata = ()
            if origin is Annotated:
                args = get_args(annotation)
                if args:
                    annotation = args[0]
                    metadata = args[1:]
            for meta in metadata:
                if isinstance(meta, Depends):
                    bound[name] = await self._resolve_dependency(
                        meta.dependency,
                        params=params,
                        headers=headers,
                        closers=closers,
                    )
                    break
            else:
                if isinstance(default, Depends):
                    bound[name] = await self._resolve_dependency(
                        default.dependency,
                        params=params,
                        headers=headers,
                        closers=closers,
                    )
                elif name in path_params:
                    bound[name] = self._convert_parameter(path_params[name], annotation)
                elif default is inspect._empty and not body_consumed and json is not None:
                    bound[name] = self._convert_body(json, annotation)
                    body_consumed = True
                elif name in params:
                    bound[name] = self._convert_parameter(params[name], annotation)
                elif isinstance(default, HeaderInfo):
                    header_key = (default.alias or name).lower()
                    header_value = headers.get(header_key)
                    bound[name] = header_value if header_value is not None else default.default
                elif default is not inspect._empty:
                    bound[name] = default
                else:
                    raise TypeError(f"Missing required parameter '{name}'")
            if name in bound:
                bound[name] = self._ensure_model(annotation, bound[name])
        return bound

    async def _resolve_dependency(
        self,
        dependency: Callable[..., Any],
        *,
        params: dict[str, Any],
        headers: dict[str, Any],
        closers: list[Callable[[], Awaitable[None] | None]],
    ) -> Any:
        kwargs = await self._build_kwargs(
            dependency,
            params=params,
            json=None,
            path_params={},
            headers=headers,
            closers=closers,
        )
        value = dependency(**kwargs)
        if inspect.isasyncgen(value):
            agen = value

            async def _aclose() -> None:
                await agen.aclose()

            try:
                resolved = await agen.__anext__()
            except StopAsyncIteration as exc:  # pragma: no cover - 防御性分支
                raise RuntimeError("Dependency generator did not yield") from exc
            closers.append(_aclose)
            return resolved
        if inspect.isgenerator(value):
            gen = value

            def _close() -> None:
                gen.close()

            try:
                resolved = next(gen)
            except StopIteration as exc:  # pragma: no cover - 防御性分支
                raise RuntimeError("Dependency generator did not yield") from exc
            closers.append(_close)
            return resolved
        if asyncio.iscoroutine(value):
            return await value
        return value

    def _convert_body(self, data: Any, annotation: Any) -> Any:
        if annotation is inspect._empty or annotation is Any:
            return data
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation.model_validate(data)
        if hasattr(annotation, "model_validate"):
            return annotation.model_validate(data)
        return data

    def _convert_parameter(self, value: Any, annotation: Any) -> Any:
        if annotation is inspect._empty or annotation is Any:
            return value
        origin = get_origin(annotation)
        if origin is Annotated:
            args = get_args(annotation)
            if args:
                annotation = args[0]
                origin = get_origin(annotation)
        if origin is None:
            return self._cast_simple(value, annotation)
        if origin in {list, tuple, set}:
            item_type = get_args(annotation)[0]
            converted = [self._convert_parameter(item, item_type) for item in value]
            return origin(converted) if origin is not tuple else tuple(converted)
        if origin is dict:
            key_type, val_type = get_args(annotation)
            return {self._convert_parameter(k, key_type): self._convert_parameter(v, val_type) for k, v in value.items()}
        if origin is type(None):
            return None
        if origin is not None:
            for arg in get_args(annotation):
                if arg is type(None):
                    if value in (None, "", "null"):
                        return None
                    continue
                try:
                    return self._convert_parameter(value, arg)
                except Exception:  # noqa: BLE001 - 宽松转换
                    continue
            return value
        return value

    def _cast_simple(self, value: Any, annotation: Any) -> Any:
        if annotation is Any:
            return value
        if isinstance(annotation, type):
            if issubclass(annotation, enum.Enum):
                return annotation(value)
            try:
                return annotation(value)
            except Exception:  # noqa: BLE001 - 宽松转换
                return value
        return value

    def _render_response(self, result: Any, response_model: Any | None) -> Any:
        if isinstance(result, PlainResponse):
            return result.content
        if isinstance(result, BaseModel):
            return result.model_dump()
        if response_model is not None and hasattr(response_model, "model_validate"):
            model = response_model.model_validate(result)
            return model.model_dump()
        if isinstance(result, list):
            return [self._render_response(item, None) for item in result]
        return result

    def _ensure_model(self, annotation: Any, value: Any) -> Any:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel) and not isinstance(value, BaseModel):
            if isinstance(value, dict):
                return annotation.model_validate(value)
        if hasattr(annotation, 'model_validate') and not isinstance(value, BaseModel):
            try:
                return annotation.model_validate(value)
            except Exception:  # noqa: BLE001
                return value
        return value


