from uuid import uuid4
from datetime import datetime
from json import JSONDecodeError
from typing import Any

import orjson
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.bgtask import BgTasks
from app.core.ctx import CTX_X_REQUEST_ID, CTX_USER_ID
from app.core.dependency import check_token
from app.core.exceptions import HTTPException
from app.models.system import LogType
from app.models.system import User, Log, APILog
from app.configs import APP_SETTINGS


class SimpleBaseMiddleware:
    """
    简化的基础中间件类
    提供更好的性能和错误处理
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await self.handle_http(scope, receive, send)

    async def handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        response = await self.before_request(request) or self.app

        async def send_wrapper(message: dict[str, Any]) -> None:
            await self.after_request(request, message)
            await send(message)

        await response(scope, receive, send_wrapper)

    async def before_request(self, request: Request) -> ASGIApp | None:
        """请求前处理"""
        return None

    async def after_request(self, request: Request, message: dict[str, Any]) -> None:
        """请求后处理"""
        pass


class BackGroundTaskMiddleware(SimpleBaseMiddleware):
    """
    后台任务中间件
    优化任务执行和错误处理
    """

    async def before_request(self, request: Request) -> ASGIApp | None:
        try:
            await BgTasks.init_bg_tasks_obj()
        except Exception as e:
            # 记录错误但不阻止请求继续
            print(f"Failed to initialize background tasks: {e}")
        return None

    async def after_request(self, request: Request, message: dict[str, Any]) -> None:
        try:
            await BgTasks.execute_tasks()
        except Exception as e:
            # 记录错误但不影响响应
            print(f"Failed to execute background tasks: {e}")


class APILoggerMiddleware(BaseHTTPMiddleware):
    """
    API日志中间件
    优化日志记录性能和错误处理
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.excluded_paths = {"/health", "/metrics", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # 设置请求开始时间和ID
        request.state.start_time = datetime.now()
        x_request_id = uuid4().hex
        CTX_X_REQUEST_ID.set(x_request_id)
        request.state.x_request_id = x_request_id

        path = request.url.path

        # 跳过不需要记录的路径
        if path in self.excluded_paths:
            return await call_next(request)

        # 检查是否需要记录日志
        should_log = self._should_log_request(path)

        if should_log and request.scope["type"] == "http":
            try:
                await self._create_api_log(request, x_request_id)
            except Exception as e:
                # 日志记录失败不应该影响请求处理
                print(f"Failed to create API log: {e}")

        response = await call_next(request)
        return response

    def _should_log_request(self, path: str) -> bool:
        """判断是否应该记录请求日志"""
        # 检查排除列表
        if any(exclude in path for exclude in APP_SETTINGS.ADD_LOG_ORIGINS_DECLUDE):
            return False

        # 检查包含列表
        if "*" in APP_SETTINGS.ADD_LOG_ORIGINS_INCLUDE:
            return True

        return any(include in path for include in APP_SETTINGS.ADD_LOG_ORIGINS_INCLUDE)

    async def _get_user_from_token(self, token: str) -> User | None:
        """从token获取用户信息"""
        try:
            status, _, decode_data = check_token(token.replace("Bearer ", "", 1))
            if status and decode_data:
                user_id = int(decode_data["data"]["userId"])
                user_obj = await User.filter(id=user_id).first()
                if user_obj:
                    CTX_USER_ID.set(user_id)
                return user_obj
        except Exception:
            pass
        return None

    async def _get_request_data(self, request: Request) -> dict[str, Any] | None:
        """安全地获取请求数据"""
        if request.method not in ["POST", "PUT", "PATCH"]:
            return None

        try:
            return await request.json()
        except (JSONDecodeError, UnicodeDecodeError, ValueError):
            return None

    async def _create_api_log(self, request: Request, x_request_id: str) -> None:
        """创建API日志记录"""
        # 获取用户信息
        token = request.headers.get("Authorization")
        user_obj = None
        if token:
            user_obj = await self._get_user_from_token(token)

        # 获取请求数据
        request_data = await self._get_request_data(request)

        # 验证URL长度
        url = str(request.url.path)
        if len(url) > 500:
            raise HTTPException(msg="请求url path过长, 请联系开发人员", code="4001")

        # 创建API日志数据
        api_log_data = {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "request_domain": request.url.hostname,
            "request_path": request.url.path,
            "request_params": dict(request.query_params) or None,
            "request_data": request_data,
            "x_request_id": x_request_id,
        }

        # 创建日志记录
        api_log_obj = await APILog.create(**api_log_data)
        request.state.api_log_id = api_log_obj.id

        # 创建系统日志
        await Log.create(log_type=LogType.ApiLog, by_user=user_obj, api_log=api_log_obj, x_request_id=x_request_id)


class APILoggerAddResponseMiddleware(SimpleBaseMiddleware):
    """
    API响应日志中间件
    优化响应数据记录和性能
    """

    async def after_request(self, request: Request, message: dict[str, Any]) -> None:
        # 处理响应体
        if message.get("type") == "http.response.body" and hasattr(request.state, "api_log_id"):
            await self._update_response_log(request, message)

        # 添加请求ID到响应头
        if message.get("type") == "http.response.start" and hasattr(request.state, "x_request_id"):
            headers = message.setdefault("headers", [])
            headers.append((b"x-request-id", request.state.x_request_id.encode()))

    async def _update_response_log(self, request: Request, message: dict[str, Any]) -> None:
        """更新响应日志"""
        try:
            response_body = message.get("body", b"")
            if not response_body:
                return

            # 解析响应数据
            try:
                resp_data = orjson.loads(response_body)
            except (orjson.JSONDecodeError, UnicodeDecodeError):
                return

            # 更新API日志
            api_log_obj = await APILog.get(id=request.state.api_log_id)
            if api_log_obj:
                api_log_obj.response_data = resp_data
                api_log_obj.response_code = resp_data.get("code", "-1")

                # 计算处理时间
                if hasattr(request.state, "start_time"):
                    process_time = (datetime.now() - request.state.start_time).total_seconds()
                    api_log_obj.process_time = process_time

                await api_log_obj.save()

        except Exception as e:
            # 记录错误但不影响响应
            print(f"Failed to update response log: {e}")
