from aerich import Command
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from tortoise.contrib.fastapi import register_tortoise
from tortoise.exceptions import DoesNotExist, IntegrityError, MultipleObjectsReturned

from app.api import api_router
from app.configs import APP_SETTINGS
from app.core.exceptions import (
    DoesNotExistHandle,
    HTTPException,
    HttpExcHandle,
    IntegrityHandle,
    RequestValidationError,
    RequestValidationHandle,
    ResponseValidationError,
    ResponseValidationHandle,
)
from app.core.middlewares import (
    APILoggerAddResponseMiddleware,
    APILoggerMiddleware,
    BackGroundTaskMiddleware,
)
from app.db.seeds.initial_data import init_menus, init_users


def make_middlewares():
    """
    创建中间件列表
    优化中间件配置，提供更好的性能和可维护性
    """
    middleware = [
        # CORS中间件 - 必须在最前面
        Middleware(
            CORSMiddleware,
            allow_origins=APP_SETTINGS.CORS_ORIGINS,
            allow_credentials=APP_SETTINGS.CORS_ALLOW_CREDENTIALS,
            allow_methods=APP_SETTINGS.CORS_ALLOW_METHODS,
            allow_headers=APP_SETTINGS.CORS_ALLOW_HEADERS,
            # 优化CORS配置
            max_age=600,  # 预检请求缓存时间
        ),
        # 后台任务中间件
        Middleware(BackGroundTaskMiddleware),
        # API日志中间件
        Middleware(APILoggerMiddleware),
        # API响应日志中间件
        Middleware(APILoggerAddResponseMiddleware),
    ]
    return middleware


def register_db(app: FastAPI):
    register_tortoise(
        app,
        config=APP_SETTINGS.TORTOISE_ORM,
        generate_schemas=True,
    )


def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)  # type: ignore
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)


def register_routers(app: FastAPI, prefix: str = "/api"):
    app.include_router(api_router, prefix=prefix)


async def modify_db():
    command = Command(tortoise_config=APP_SETTINGS.TORTOISE_ORM, app="models")
    try:
        # 首先尝试初始化数据库
        await command.init_db(safe=True)
        logger.info("Database initialized successfully")
    except FileExistsError:
        logger.info("Database already exists")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")

    try:
        # 初始化 Aerich
        await command.init()
        logger.info("Aerich initialized successfully")
    except Exception as e:
        logger.warning(f"Aerich initialization failed: {e}")

    try:
        # 生成迁移
        await command.migrate()
        logger.info("Migration generated successfully")
    except Exception as e:
        logger.warning(f"Migration generation failed: {e}")

    try:
        # 应用迁移
        await command.upgrade(run_in_transaction=True)
        logger.info("Migration applied successfully")
    except Exception as e:
        logger.warning(f"Migration application failed: {e}")


# init_menus and init_users are now imported from app.db.seeds.initial_data
# This file is much cleaner now.
