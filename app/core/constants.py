from enum import Enum

class ErrorCode(str, Enum):
    """业务错误码枚举"""
    SUCCESS = "0000"
    ERROR = "9999"
    
    # 认证授权相关
    AUTH_FAILED = "4001"  # 认证失败（Token无效/缺失）
    AUTH_LOGIN_FAILED = "4040"  # 登录失败（账号密码错误/被禁用）
    AUTH_FORBIDDEN = "403"   # 权限不足
    
    # 业务逻辑相关
    DATA_ALREADY_EXISTS = "4090"  # 数据已存在
    DATA_NOT_FOUND = "404"        # 数据不存在
    PARAM_ERROR = "422"           # 参数错误
    
    # 系统相关
    SYSTEM_ERROR = "5000"    # 系统内部错误
    EXTERNAL_API_ERROR = "5001"  # 外部接口调用失败
