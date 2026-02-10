from fastapi import APIRouter
from .v1 import v1_router

# 创建主API路由器
api_router = APIRouter(
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    }
)

# 包含v1版本路由
api_router.include_router(
    v1_router,
    prefix="/v1",
    tags=["API v1"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    },
)
