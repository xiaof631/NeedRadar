from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Response:
    """最小化 Response 对象，用于返回原始内容。"""

    content: Any
    media_type: str | None = None
