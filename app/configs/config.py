"""FeelyAdmin 配置管理模块

使用 Dynaconf 进行配置管理，支持多环境配置和动态配置加载。
配置文件位于 app/settings/ 目录下。

主要功能：
- 多环境配置支持 (development, testing, production)
- 配置验证和类型转换
- 数据库和 Redis 连接配置
- JWT 和 CORS 配置管理
"""

from pathlib import Path
from typing import Any
from dynaconf import Dynaconf, Validator

# 项目根目录和配置目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
CONFIG_DIR = PROJECT_ROOT / "app" / "settings"

# 配置验证器
validators = [
    # 应用配置验证 - 只在 default 环境验证
    Validator("VERSION", must_exist=True, is_type_of=str, env="default"),
    Validator("APP_TITLE", must_exist=True, is_type_of=str, env="default"),
    Validator("APP_DESCRIPTION", must_exist=True, is_type_of=str, env="default"),
    Validator("DEBUG", must_exist=True, is_type_of=bool),
    # 安全配置验证
    Validator("SECRET_KEY", must_exist=True, is_type_of=str, env="default"),
    Validator("JWT_SECRET_KEY", must_exist=False, is_type_of=str),
    # JWT 配置 - 只在 default 环境验证
    Validator("JWT_ALGORITHM", must_exist=True, is_type_of=str, is_in=["HS256", "HS384", "HS512"], env="default"),
    Validator("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", must_exist=True, is_type_of=int, gte=1, env="default"),
    Validator("JWT_REFRESH_TOKEN_EXPIRE_MINUTES", must_exist=True, is_type_of=int, gte=1, env="default"),
    # CORS 配置 - 只在 default 环境验证
    Validator("CORS_ORIGINS", must_exist=True, is_type_of=list, env="default"),
    Validator("CORS_ALLOW_CREDENTIALS", must_exist=True, is_type_of=bool, env="default"),
    Validator("CORS_ALLOW_METHODS", must_exist=True, is_type_of=list, env="default"),
    Validator("CORS_ALLOW_HEADERS", must_exist=True, is_type_of=list, env="default"),
    # 数据库配置 - 只在 default 环境验证
    Validator("DATABASE.engine", must_exist=True, is_type_of=str, env="default"),
    Validator("DATABASE.host", must_exist=True, is_type_of=str, env="default"),
    Validator("DATABASE.port", must_exist=True, is_type_of=int, gte=1, lte=65535, env="default"),
    Validator("DATABASE.user", must_exist=True, is_type_of=str, env="default"),
    Validator("DATABASE.database", must_exist=True, is_type_of=str, env="default"),
    Validator("DATABASE.charset", default="utf8mb4", is_type_of=str, env="default"),
    Validator("DATABASE.timezone", default="Asia/Shanghai", is_type_of=str, env="default"),
    Validator("DATABASE.use_tz", default=False, is_type_of=bool, env="default"),
    # MySQL 连接池配置 - 只在 default 环境验证
    Validator("DATABASE.minsize", default=1, is_type_of=int, gte=1, env="default"),
    Validator("DATABASE.maxsize", default=20, is_type_of=int, gte=1, env="default"),
    Validator("DATABASE.connect_timeout", default=30, is_type_of=int, gte=1, env="default"),
    Validator("DATABASE.echo", default=False, is_type_of=bool, env="default"),
    # Redis 配置 - 只在 default 环境验证
    Validator("REDIS.url", must_exist=True, is_type_of=str, env="default"),
    # 时间格式配置
    Validator("DATETIME_FORMAT", default="%Y-%m-%d %H:%M:%S", is_type_of=str),
    # API 日志记录配置 - 只在 default 环境验证
    Validator("ADD_LOG_ORIGINS_INCLUDE", default=["*"], is_type_of=list, env="default"),
    Validator(
        "ADD_LOG_ORIGINS_DECLUDE",
        default=["/health", "/metrics", "/favicon.ico", "/docs", "/redoc", "/openapi.json"],
        is_type_of=list,
        env="default",
    ),
]

# 初始化 Dynaconf 设置
settings = Dynaconf(
    settings_files=[
        str(CONFIG_DIR / "settings.toml"),
        str(CONFIG_DIR / ".secrets.toml"),
    ],
    environments=True,
    env="development",
    # 统一设置环境变量前缀，支持使用 FeelyAdmin_* 来覆盖配置
    envvar_prefix="FeelyAdmin",
    load_dotenv=True,
    merge_enabled=True,
    auto_cast=True,
    validators=validators,
)


class ConfigProxy:
    """配置代理类，提供统一的配置访问接口"""

    def __init__(self, dynaconf_settings):
        self._settings = dynaconf_settings

    def __getattr__(self, name):
        """获取配置项，优先从当前环境获取，然后从 default 获取"""
        # 特殊处理 current_env
        if name == "current_env":
            return self._settings.current_env

        # 特殊处理 TORTOISE_ORM
        if name == "TORTOISE_ORM":
            return get_tortoise_orm_config()

        # 特殊处理 REDIS_URL
        if name == "REDIS_URL":
            return self.REDIS.url

        try:
            # 先尝试从当前环境获取
            value = getattr(self._settings, name, None)
            if value is not None:
                return self._process_value(name, value)
        except AttributeError:
            pass

        try:
            # 如果当前环境没有，尝试从 default 获取
            value = getattr(self._settings.default, name, None)
            if value is not None:
                return self._process_value(name, value)
        except AttributeError:
            pass

        raise AttributeError(f"配置项 '{name}' 不存在")

    def _process_value(self, name: str, value: Any) -> Any:
        """处理配置值，进行类型转换"""
        # 路径相关配置转换为 Path 对象
        if name in ("LOGS_ROOT", "STATIC_ROOT") and isinstance(value, str):
            return PROJECT_ROOT / value
        return value

    def get(self, name, default=None):
        """安全获取配置项"""
        try:
            return self.__getattr__(name)
        except AttributeError:
            return default

    @property
    def current_env(self):
        """获取当前环境"""
        return self._settings.current_env


# 创建配置代理实例
config = ConfigProxy(settings)


def get_tortoise_orm_config(engine: str | None = None) -> dict[str, Any]:
    """
    生成 TortoiseORM 配置

    Args:
        engine: 数据库引擎，如果不提供则使用配置中的引擎

    Returns:
        TortoiseORM 配置字典
    """
    db_engine = engine or config.DATABASE.engine

    # 根据数据库引擎生成不同的连接配置
    if "sqlite" in db_engine:
        # SQLite 配置
        credentials = {
            "file_path": config.DATABASE.database,
        }
        engine_name = "tortoise.backends.sqlite"
    elif "mysql" in db_engine:
        # MySQL 配置
        credentials = {
            "host": config.DATABASE.host,
            "port": config.DATABASE.port,
            "user": config.DATABASE.user,
            "database": config.DATABASE.database,
            "charset": config.DATABASE.charset,
            "minsize": config.DATABASE.minsize,
            "maxsize": config.DATABASE.maxsize,
            "connect_timeout": config.DATABASE.connect_timeout,
            "echo": config.DATABASE.echo,
        }

        # 添加密码（MySQL 要求必须有 password 参数）
        password = getattr(config.DATABASE, "password", "")
        credentials["password"] = password
        engine_name = "tortoise.backends.mysql"
    elif "asyncpg" in db_engine or "postgresql" in db_engine:
        # PostgreSQL 配置
        credentials = {
            "host": config.DATABASE.host,
            "port": config.DATABASE.port,
            "user": config.DATABASE.user,
            "database": config.DATABASE.database,
            "minsize": config.DATABASE.minsize,
            "maxsize": config.DATABASE.maxsize,
        }

        # 添加密码（如果存在且不为空）
        password = getattr(config.DATABASE, "password", None)
        if password:
            credentials["password"] = password
        engine_name = "tortoise.backends.asyncpg"
    else:
        raise ValueError(f"不支持的数据库引擎: {db_engine}")

    return {
        "connections": {
            "default": {
                "engine": engine_name,
                "credentials": credentials,
            }
        },
        "apps": {
            "models": {
                "models": ["app.models", "aerich.models"],
                "default_connection": "default",
            }
        },
        "use_tz": config.DATABASE.use_tz,
        "timezone": config.DATABASE.timezone,
    }


def get_database_url() -> str:
    """
    构建数据库连接 URL

    Returns:
        数据库连接 URL 字符串
    """
    engine = config.DATABASE.engine

    if engine == "tortoise.backends.sqlite":
        file_path = getattr(config.DATABASE, "file_path", "app_system.sqlite3")
        return f"sqlite://{file_path}"

    elif engine == "tortoise.backends.mysql":
        password = getattr(config.DATABASE, "password", "")
        password_part = f":{password}" if password else ""
        return (
            f"mysql://{config.DATABASE.user}{password_part}"
            f"@{config.DATABASE.host}:{config.DATABASE.port}"
            f"/{config.DATABASE.database}"
        )

    elif engine == "tortoise.backends.asyncpg":
        password = getattr(config.DATABASE, "password", "")
        password_part = f":{password}" if password else ""
        return (
            f"postgresql://{config.DATABASE.user}{password_part}"
            f"@{config.DATABASE.host}:{config.DATABASE.port}"
            f"/{config.DATABASE.database}"
        )

    else:
        raise ValueError(f"不支持的数据库引擎: {engine}")


def get_redis_url() -> str:
    """
    获取 Redis 连接 URL

    Returns:
        Redis 连接 URL 字符串
    """
    return config.REDIS.url


def get_current_env() -> str:
    """
    获取当前环境名称

    Returns:
        当前环境名称
    """
    return config.current_env.lower()


def validate_config() -> None:
    """
    验证配置的有效性

    Raises:
        ValidationError: 当配置验证失败时
    """
    settings.validators.validate()


def get_config_summary() -> dict[str, Any]:
    """
    获取配置摘要信息（用于调试和监控）

    Returns:
        配置摘要字典
    """
    return {
        "current_env": get_current_env(),
        "app_title": config.APP_TITLE,
        "debug": config.DEBUG,
        "database_engine": config.DATABASE.engine,
        "database_host": config.DATABASE.host,
        "redis_url": config.REDIS.url,
        "config_files": [
            str(CONFIG_DIR / "settings.toml"),
            str(CONFIG_DIR / ".secrets.toml"),
        ],
    }


# 导出的公共接口
__all__ = [
    "config",
    "settings",
    "get_tortoise_orm_config",
    "get_database_url",
    "get_redis_url",
    "get_current_env",
    "validate_config",
    "get_config_summary",
    "PROJECT_ROOT",
    "CONFIG_DIR",
]
