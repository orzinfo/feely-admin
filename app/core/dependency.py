from typing import Any

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.core.ctx import CTX_USER_ID, CTX_X_REQUEST_ID
from app.core.exceptions import HTTPException
from app.log import log
from app.models.system import User, StatusType
from app.configs import APP_SETTINGS
from app.utils.tools import check_url

# OAuth2 认证方案
oauth2_schema = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _decode_token(token: str, secret_key: str, algorithm: str) -> tuple[bool, int, Any]:
    """Token解码函数"""
    try:
        options = {"verify_signature": True, "verify_aud": False, "exp": True}
        decode_data = jwt.decode(token, secret_key, algorithms=[algorithm], options=options)
        return True, 0, decode_data
    except jwt.DecodeError:
        return False, 8888, "无效的Token"
    except jwt.ExpiredSignatureError:
        return False, 4010, "登录已过期"
    except Exception as e:
        return False, 5000, f"{repr(e)}"


def check_token(token: str) -> tuple[bool, int, Any]:
    """检查token有效性"""
    return _decode_token(token, APP_SETTINGS.SECRET_KEY, APP_SETTINGS.JWT_ALGORITHM)


class AuthControl:
    """认证控制器"""

    @classmethod
    async def is_authed(cls, token: str = Depends(oauth2_schema)) -> User:
        """
        验证用户认证状态

        Args:
            token: JWT token

        Returns:
            User: 认证用户对象

        Raises:
            HTTPException: 认证失败时抛出异常
        """
        if not token:
            raise HTTPException(code="4001", msg="Authentication failed, token does not exists in the request.")

        # 从上下文获取用户ID（如果已设置）
        user_id = CTX_USER_ID.get()
        if user_id == 0:
            status, code, decode_data = check_token(token)
            if not status:
                raise HTTPException(code=code, msg=decode_data)

            if decode_data["data"]["tokenType"] != "accessToken":
                raise HTTPException(code="4040", msg="The token is not an access token")

            user_id = decode_data["data"]["userId"]

        # 查询用户信息
        user = await User.filter(id=user_id).first()
        if not user:
            raise HTTPException(
                code="4040", msg=f"Authentication failed, the user_id: {user_id} does not exists in the system."
            )

        # 设置上下文用户ID
        CTX_USER_ID.set(int(user_id))
        return user

    @classmethod
    async def get_current_user_optional(cls, token: str = Depends(oauth2_schema)) -> User | None:
        """
        获取当前用户（可选）

        Args:
            token: JWT token

        Returns:
            Optional[User]: 用户对象或None
        """
        try:
            return await cls.is_authed(token)
        except HTTPException:
            return None


class PermissionControl:
    """权限控制器"""

    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        """
        检查用户权限

        Args:
            request: FastAPI请求对象
            current_user: 当前认证用户

        Raises:
            HTTPException: 权限不足时抛出异常
        """
        # 预加载用户角色及其关联的API
        await current_user.fetch_related("by_user_roles__by_role_apis")
        user_roles_codes: list[str] = [r.role_code for r in current_user.by_user_roles]

        # 超级管理员直接通过
        if "R_SUPER" in user_roles_codes:
            return

        if not current_user.by_user_roles:
            raise HTTPException(code="4040", msg="The user is not bound to a role")

        method = request.method.lower()
        path = request.url.path

        # 获取用户所有API权限
        apis = [role.by_role_apis for role in current_user.by_user_roles]
        permission_apis = list(set((api.api_method.value, api.api_path, api.status_type) for api in sum(apis, [])))

        # 检查权限
        for api_method, api_path, api_status in permission_apis:
            if api_method == method and check_url(api_path, request.url.path):
                if api_status == StatusType.disable:
                    raise HTTPException(code="4031", msg=f"The API has been disabled, method: {method} path: {path}")
                return

        # 权限检查失败，记录日志
        log.error("*" * 20)
        log.error(f"Permission denied, method: {method.upper()} path: {path}")
        log.error(f"x-request-id: {CTX_X_REQUEST_ID.get()}")
        log.error("*" * 20)
        raise HTTPException(code="4032", msg=f"Permission denied, method: {method} path: {path}")


# 常用依赖注入快捷方式
DependAuth = Depends(AuthControl.is_authed)
DependAuthOptional = Depends(AuthControl.get_current_user_optional)
DependPermission = Depends(PermissionControl.has_permission)
