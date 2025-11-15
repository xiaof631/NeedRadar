"""FastAPI 应用入口。"""

from app.api import routes
from app.core.config import settings
from app.core.logging import configure_logging
from fastapi import FastAPI

configure_logging()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(routes.api_router)


@app.get("/health", summary="健康检查")
async def health_check() -> dict[str, str]:
    """用于健康探测的接口。"""

    return {"status": "ok"}
