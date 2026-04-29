"""API 级依赖项。"""

from __future__ import annotations

from app.core.config import _normalize_api_tokens as _parse_api_tokens
from app.core.config import get_settings
from fastapi import Header, HTTPException, Query, status


async def verify_api_token(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_token: str | None = Query(default=None, description="API Token"),
) -> None:
    """在配置了 Token 时验证请求身份。"""

    settings = get_settings()
    tokens = _parse_api_tokens(settings.api_tokens)
    if not tokens:
        return

    provided = x_api_key or api_token
    if provided and provided in tokens:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="缺少或无效的 API Token",
    )
