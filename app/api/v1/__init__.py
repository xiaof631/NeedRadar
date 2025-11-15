"""v1 版本 API 路由。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="基础连通性测试")
async def ping() -> dict[str, str]:
    """用于 API 版本的连通性测试。"""

    return {"message": "pong"}
