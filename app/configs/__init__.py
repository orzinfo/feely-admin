"""
FastSoyAdmin 配置模块

使用 Dynaconf 进行现代化配置管理，提供统一的配置访问接口。
配置文件位于 app/settings/ 目录下。
"""

# 导入核心配置管理
from .config import (
    config,
    get_tortoise_orm_config,
    get_database_url,
    get_redis_url,
    get_current_env,
    validate_config,
    get_config_summary,
)

# 主要配置接口 - 保持向后兼容
APP_SETTINGS = config

# 导出核心接口
__all__ = [
    "APP_SETTINGS",
    "config",
    "get_tortoise_orm_config",
    "get_database_url", 
    "get_redis_url",
    "get_current_env",
    "validate_config",
    "get_config_summary",
]
