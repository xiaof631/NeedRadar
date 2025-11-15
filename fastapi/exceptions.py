"""FastAPI 异常类型。"""

from __future__ import annotations

from typing import Any


class HTTPException(Exception):
    """HTTP 异常对象。"""

    def __init__(self, status_code: int, detail: Any = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
