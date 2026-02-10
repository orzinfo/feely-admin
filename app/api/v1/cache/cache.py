"""
缓存管理API
提供缓存监控、预热和清理功能
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Depends

from app.core.cache import cache_manager
from app.core.dependency import AuthControl
from app.models.system import User
from app.log import log

router = APIRouter(prefix="/cache", tags=["缓存管理"])


@router.get("/health", summary="缓存健康检查")
async def cache_health_check() -> dict[str, Any]:
    """
    检查Redis缓存服务健康状态
    返回连接状态、响应时间、内存使用等信息
    """
    try:
        health_info = await cache_manager.health_check()
        return {"code": 200, "message": "Cache health check completed", "data": health_info}
    except Exception as e:
        log.error(f"Cache health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache health check failed: {str(e)}")


@router.get("/stats", summary="缓存统计信息")
async def cache_stats(current_user: User = Depends(AuthControl.is_authed)) -> dict[str, Any]:
    """
    获取缓存统计信息
    包括命中率、请求次数、平均响应时间等
    """
    try:
        stats = cache_manager.stats.copy()
        stats["hit_rate_percent"] = cache_manager.get_hit_rate()

        return {"code": 200, "message": "Cache statistics retrieved successfully", "data": stats}
    except Exception as e:
        log.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.post("/preload", summary="缓存预热")
async def cache_preload(current_user: User = Depends(AuthControl.is_authed)) -> dict[str, Any]:
    """
    执行缓存预热操作
    预加载常用数据到Redis缓存中
    """
    try:
        # 检查用户权限（这里简化处理，实际应该检查管理员权限）
        if not current_user:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        preload_result = await cache_manager.preload_cache()

        log.info(f"Cache preload initiated by user {current_user.id}")

        return {"code": 200, "message": "Cache preload completed", "data": preload_result}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Cache preload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache preload failed: {str(e)}")


@router.delete("/clear", summary="清理缓存")
async def cache_clear(
    pattern: str = "fastapi-cache:*", current_user: User = Depends(AuthControl.is_authed)
) -> dict[str, Any]:
    """
    清理缓存数据

    Args:
        pattern: 要清理的缓存键模式，默认清理所有FastAPI缓存
    """
    try:
        # 检查用户权限（这里简化处理，实际应该检查管理员权限）
        if not current_user:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        clear_result = await cache_manager.clear_cache(pattern)

        log.info(f"Cache cleared by user {current_user.id}, pattern: {pattern}")

        return {"code": 200, "message": "Cache cleared successfully", "data": clear_result}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {str(e)}")


@router.get("/info", summary="缓存详细信息")
async def cache_info(current_user: User = Depends(AuthControl.is_authed)) -> dict[str, Any]:
    """
    获取Redis缓存详细信息
    包括内存使用、连接数、配置信息等
    """
    try:
        health_info = await cache_manager.health_check()
        stats = cache_manager.stats.copy()
        stats["hit_rate_percent"] = cache_manager.get_hit_rate()

        return {
            "code": 200,
            "message": "Cache information retrieved successfully",
            "data": {
                "health": health_info,
                "statistics": stats,
                "configuration": {
                    "redis_url": "redis://redis:6379/0",  # 不暴露完整URL
                    "default_expire": 300,
                    "max_connections": 20,
                },
            },
        }
    except Exception as e:
        log.error(f"Failed to get cache info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache info: {str(e)}")
