"""
Redis缓存管理模块
提供缓存预热、监控和优化功能
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from redis import asyncio as aioredis
from redis.exceptions import ConnectionError, TimeoutError
from fastapi_cache import FastAPICache
from loguru import logger

from app.configs import APP_SETTINGS


class CacheManager:
    """Redis缓存管理器"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_requests": 0,
            "avg_response_time": 0.0
        }
    
    async def initialize(self) -> None:
        """初始化Redis连接"""
        try:
            self.redis = aioredis.from_url(
                url=APP_SETTINGS.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                retry_on_error=[ConnectionError, TimeoutError],
                health_check_interval=30,
                socket_keepalive=True,
                socket_keepalive_options={},
                max_connections=20,  # 直接使用max_connections参数
            )
            logger.info("Cache manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cache manager: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Redis健康检查"""
        if not self.redis:
            return {"status": "error", "message": "Redis not initialized"}
        
        try:
            start_time = time.time()
            await self.redis.ping()
            response_time = (time.time() - start_time) * 1000
            
            info = await self.redis.info()
            memory_usage = info.get('used_memory_human', 'Unknown')
            connected_clients = info.get('connected_clients', 0)
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "memory_usage": memory_usage,
                "connected_clients": connected_clients,
                "stats": self.stats
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def preload_cache(self) -> Dict[str, Any]:
        """缓存预热"""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        preload_results = {
            "started_at": datetime.now().isoformat(),
            "items_preloaded": 0,
            "errors": [],
            "duration_seconds": 0
        }
        
        start_time = time.time()
        
        try:
            # 预热常用数据
            preload_tasks = [
                self._preload_system_config(),
                self._preload_user_permissions(),
                self._preload_menu_data(),
                self._preload_route_data()
            ]
            
            results = await asyncio.gather(*preload_tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    preload_results["errors"].append(f"Task {i}: {str(result)}")
                else:
                    preload_results["items_preloaded"] += result
            
            preload_results["duration_seconds"] = round(time.time() - start_time, 2)
            preload_results["status"] = "completed" if not preload_results["errors"] else "partial"
            
            logger.info(f"Cache preload completed: {preload_results['items_preloaded']} items in {preload_results['duration_seconds']}s")
            
        except Exception as e:
            preload_results["status"] = "failed"
            preload_results["errors"].append(str(e))
            logger.error(f"Cache preload failed: {e}")
        
        return preload_results
    
    async def _preload_system_config(self) -> int:
        """预热系统配置"""
        try:
            # 模拟预热系统配置数据
            config_keys = [
                "system:settings",
                "system:features",
                "system:maintenance"
            ]
            
            for key in config_keys:
                await self.redis.setex(
                    f"fastapi-cache:{key}",
                    300,  # 5分钟过期
                    f"preloaded_config_{key}"
                )
            
            return len(config_keys)
        except Exception as e:
            logger.error(f"Failed to preload system config: {e}")
            raise
    
    async def _preload_user_permissions(self) -> int:
        """预热用户权限数据"""
        try:
            # 模拟预热用户权限数据
            permission_keys = [
                "permissions:admin",
                "permissions:user",
                "permissions:guest"
            ]
            
            for key in permission_keys:
                await self.redis.setex(
                    f"fastapi-cache:{key}",
                    600,  # 10分钟过期
                    f"preloaded_permissions_{key}"
                )
            
            return len(permission_keys)
        except Exception as e:
            logger.error(f"Failed to preload user permissions: {e}")
            raise
    
    async def _preload_menu_data(self) -> int:
        """预热菜单数据"""
        try:
            # 模拟预热菜单数据
            menu_keys = [
                "menu:main",
                "menu:admin",
                "menu:user"
            ]
            
            for key in menu_keys:
                await self.redis.setex(
                    f"fastapi-cache:{key}",
                    1800,  # 30分钟过期
                    f"preloaded_menu_{key}"
                )
            
            return len(menu_keys)
        except Exception as e:
            logger.error(f"Failed to preload menu data: {e}")
            raise
    
    async def _preload_route_data(self) -> int:
        """预热路由数据"""
        try:
            # 模拟预热路由数据
            route_keys = [
                "routes:constant",
                "routes:user",
                "routes:admin"
            ]
            
            for key in route_keys:
                await self.redis.setex(
                    f"fastapi-cache:{key}",
                    900,  # 15分钟过期
                    f"preloaded_routes_{key}"
                )
            
            return len(route_keys)
        except Exception as e:
            logger.error(f"Failed to preload route data: {e}")
            raise
    
    async def clear_cache(self, pattern: str = "fastapi-cache:*") -> Dict[str, Any]:
        """清理缓存"""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                deleted_count = await self.redis.delete(*keys)
                logger.info(f"Cleared {deleted_count} cache keys matching pattern: {pattern}")
                return {
                    "status": "success",
                    "deleted_count": deleted_count,
                    "pattern": pattern
                }
            else:
                return {
                    "status": "success",
                    "deleted_count": 0,
                    "pattern": pattern,
                    "message": "No keys found matching pattern"
                }
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return {
                "status": "error",
                "message": str(e),
                "pattern": pattern
            }
    
    def update_stats(self, hit: bool, response_time: float) -> None:
        """更新缓存统计"""
        self.stats["total_requests"] += 1
        if hit:
            self.stats["hits"] += 1
        else:
            self.stats["misses"] += 1
        
        # 计算平均响应时间
        current_avg = self.stats["avg_response_time"]
        total_requests = self.stats["total_requests"]
        self.stats["avg_response_time"] = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )
    
    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.stats["hits"] + self.stats["misses"]
        if total == 0:
            return 0.0
        return round((self.stats["hits"] / total) * 100, 2)


# 全局缓存管理器实例
cache_manager = CacheManager()