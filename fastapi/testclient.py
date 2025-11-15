from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .application import FastAPI
from .exceptions import HTTPException


@dataclass
class Response:
    status_code: int
    _json: Any

    def json(self) -> Any:
        return self._json


class TestClient:
    """同步测试客户端，通过事件循环执行异步处理函数。"""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def __enter__(self) -> "TestClient":
        self.app.trigger_startup()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.app.trigger_shutdown()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Response:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Any | None = None) -> Response:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: Any | None = None) -> Response:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> Response:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> Response:
        try:
            status_code, payload = asyncio.run(self.app.dispatch(method, path, params=params, json=json))
        except HTTPException as exc:
            return Response(status_code=exc.status_code, _json={"detail": exc.detail})
        except LookupError:
            return Response(status_code=404, _json={"detail": "Not Found"})
        if payload is None:
            payload = {}
        return Response(status_code=status_code, _json=payload)
