from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from redis.exceptions import ConnectionError, TimeoutError
from starlette.staticfiles import StaticFiles

from app.api.v1.utils import refresh_api_list
from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    init_menus,
    init_users,
    make_middlewares,
    modify_db,
    register_db,
    register_exceptions,
    register_routers,
)
from app.core.cache import cache_manager
from app.log import log
from app.models.system import Log
from app.models.system import LogType, LogDetailType

try:
    from app.configs import APP_SETTINGS
except ImportError:
    raise SettingNotFound("Can not import settings")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理器
    优化启动和关闭流程，提供更好的错误处理和日志记录
    """
    start_time = datetime.now()
    
    # 启动阶段
    try:
        log.info(f"Starting {app.title} v{app.version}")
        
        # 初始化数据库
        await modify_db()
        log.info("Database initialization completed")
        
        # 初始化菜单
        await init_menus()
        log.info("Menu initialization completed")
        
        # 刷新API列表
        await refresh_api_list()
        log.info("API list refresh completed")
        
        # 初始化用户
        await init_users()
        log.info("User initialization completed")
        
        # 初始化缓存管理器
        try:
            await cache_manager.initialize()
            log.info("Cache manager initialization completed")
        except Exception as e:
            log.warning(f"Cache manager initialization failed: {e}")
            log.info("Application will continue without cache functionality")
        
        # 执行缓存预热 - 临时禁用以避免Redis连接错误
        try:
            preload_result = await cache_manager.preload_cache()
            log.info(f"Cache preload completed: {preload_result.get('items_preloaded', 0)} items")
        except Exception as e:
            log.warning(f"Cache preload skipped due to Redis connection issue: {e}")
            log.info("Application will continue without cache preload")
        
        # 记录系统启动日志
        await Log.create(
            log_type=LogType.SystemLog, 
            log_detail_type=LogDetailType.SystemStart
        )
        
        startup_time = (datetime.now() - start_time).total_seconds()
        log.info(f"Application {app.title} started successfully in {startup_time:.2f} seconds")
        
        yield
        
    except Exception as e:
        log.error(f"Failed to start application: {e}")
        raise
    
    # 关闭阶段
    finally:
        try:
            end_time = datetime.now()
            runtime = (end_time - start_time).total_seconds() / 60
            
            # 记录系统停止日志
            await Log.create(
                log_type=LogType.SystemLog, 
                log_detail_type=LogDetailType.SystemStop
            )
            
            log.info(f"Application {app.title} runtime: {runtime:.2f} minutes")
            log.info("Application shutdown completed")
            
        except Exception as e:
            log.error(f"Error during application shutdown: {e}")


def create_app() -> FastAPI:
    """
    创建FastAPI应用实例
    优化配置结构，提供更好的开发和生产环境支持
    """
    # 基础应用配置
    app_config = {
        "title": APP_SETTINGS.APP_TITLE,
        "description": APP_SETTINGS.APP_DESCRIPTION,
        "version": APP_SETTINGS.VERSION,
        "lifespan": lifespan,
    }
    
    # 根据环境配置OpenAPI
    if APP_SETTINGS.DEBUG:
        app_config.update({
            "openapi_url": "/openapi.json",
            "docs_url": "/docs",
            "redoc_url": "/redoc",
        })
    else:
        app_config.update({
            "openapi_url": None,
            "docs_url": None,
            "redoc_url": None,
        })
    
    # 创建应用实例
    _app = FastAPI(**app_config)
    
    # 添加中间件
    middlewares = make_middlewares()
    for middleware in middlewares:
        _app.add_middleware(middleware.cls, **middleware.kwargs)
    
    # 注册组件
    register_db(_app)
    register_exceptions(_app)
    register_routers(_app, prefix="/api")
    
    # 初始化缓存
    _init_cache()
    
    # 挂载静态文件
    _app.mount("/static", StaticFiles(directory=APP_SETTINGS.STATIC_ROOT), name="static")
    
    return _app


def _init_cache() -> None:
    """
    初始化Redis缓存
    利用Redis 7.0.1的新特性，提供更好的缓存配置和错误处理
    """
    try:
        # Redis 7.0.1 优化配置 - 修复connection_pool_kwargs参数问题
        redis = aioredis.from_url(
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
        
        # 初始化FastAPI缓存后端
        FastAPICache.init(
            RedisBackend(redis), 
            prefix="fastapi-cache",
            expire=300,  # 默认5分钟过期
            key_builder=lambda func, namespace, request, response, *args, **kwargs: (
                f"{namespace}:{func.__module__}:{func.__name__}:"
                f"{hash(str(sorted(request.query_params.items())))}"
            )
        )
        log.info("Redis cache initialized successfully with optimized configuration")
    except Exception as e:
        log.error(f"Failed to initialize Redis cache: {e}")
        raise


# 创建应用实例
app = create_app()
