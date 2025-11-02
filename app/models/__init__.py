"""
FastSoyAdmin 数据模型模块

该模块导入所有数据模型，确保 TortoiseORM 能够正确发现和注册模型。
"""

# 导入系统管理相关模型
from app.models.system.admin import *
from app.models.system.utils import *

# 确保所有模型都被导入，以便 TortoiseORM 能够发现它们
__all__ = [
    # 系统管理模型
    "User", "Role", "Menu", "Button", "Log", "Api",
    # 工具模型
    "BaseModel", "TimestampMixin", "StatusType", "MenuType", "IconType"
]