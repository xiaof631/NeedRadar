"""FastAPI 应用入口。"""

from app.api import routes
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.metrics import instrument_fastapi_app, metrics_router
from app.core.telemetry import instrument_app
from fastapi import FastAPI

configure_logging()

app = FastAPI(title=settings.app_name, debug=settings.debug)
instrument_app(app)
instrument_fastapi_app(app)
app.include_router(metrics_router)
app.include_router(routes.api_router)


@app.get("/health", summary="健康检查")
async def health_check() -> dict[str, str]:
    """用于健康探测的接口。"""

    return {"status": "ok"}
