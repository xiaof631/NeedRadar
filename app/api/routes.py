"""API 路由入口。"""

from app.api import deps
from app.api.v1 import router as v1_router
from fastapi import APIRouter, Depends

api_router = APIRouter(dependencies=[Depends(deps.verify_api_token)])
api_router.include_router(v1_router, prefix="/api/v1")
