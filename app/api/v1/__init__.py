from fastapi import APIRouter

from .auth import router_auth
from .route import router_route
from .system_manage import router_system_manage
from .cache import router as router_cache

# 创建v1版本路由器
v1_router = APIRouter()

# 认证相关路由
v1_router.include_router(
    router_auth,
    prefix="/auth",
    tags=["权限认证"],
    responses={
        401: {"description": "认证失败"},
        403: {"description": "权限不足"},
    },
)

# 路由管理
v1_router.include_router(
    router_route,
    prefix="/route",
    tags=["路由管理"],
    responses={
        404: {"description": "路由不存在"},
    },
)

# 系统管理
v1_router.include_router(
    router_system_manage,
    prefix="/system-manage",
    tags=["系统管理"],
    responses={
        403: {"description": "需要管理员权限"},
    },
)

# 缓存管理
v1_router.include_router(
    router_cache,
    tags=["缓存管理"],
    responses={
        403: {"description": "需要管理员权限"},
        500: {"description": "缓存服务异常"},
    },
)
