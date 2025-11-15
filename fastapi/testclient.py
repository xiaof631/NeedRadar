"""测试客户端的极简实现。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .application import FastAPI


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

    def get(self, path: str, params: dict[str, Any] | None = None) -> Response:
        try:
            if params:
                result = asyncio.run(self.app.dispatch("GET", path, **params))
            else:
                result = asyncio.run(self.app.dispatch("GET", path))
        except LookupError:
            return Response(status_code=404, _json={"detail": "Not Found"})
        return Response(status_code=200, _json=result)
