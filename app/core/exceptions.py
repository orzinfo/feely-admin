import http

import orjson
from fastapi.exceptions import (
    RequestValidationError,
    ResponseValidationError,
)
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from tortoise.exceptions import DoesNotExist, IntegrityError

from app.core.ctx import CTX_X_REQUEST_ID


class SettingNotFound(Exception):
    pass


class HTTPException(Exception):
    def __init__(self, code: int | str, msg: str | None = None) -> None:
        if msg is None:
            msg = http.HTTPStatus(int(code)).phrase
        self.code = code
        self.msg = msg

    def __str__(self) -> str:
        return f"{self.code}: {self.msg}"

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(code={self.code!r}, msg={self.msg!r})"


async def BaseHandle(
    req: Request, exc: Exception, handle_exc, code: int | str, msg: str | dict, status_code: int = 500, **kwargs
) -> JSONResponse:
    headers = {"x-request-id": CTX_X_REQUEST_ID.get() or ""}
    # request_body = await req.body() or {}
    # try:
    #     request_body = orjson.loads(request_body)
    # except (orjson.JSONDecodeError, UnicodeDecodeError):
    #     request_body = {}

    request_input = {
        "path": req.url.path,
        "query": dict(req.query_params),
        # "body": request_body,
        # "headers": dict(req.headers),
    }
    content = dict(code=str(code), x_request_id=headers["x-request-id"], msg=msg, input=request_input, **kwargs)
    if isinstance(exc, handle_exc):
        return JSONResponse(content=content, status_code=status_code)
    else:
        return JSONResponse(
            content=dict(code=str(code), msg=f"Exception handler Error, exc: {exc}"), status_code=status_code
        )


async def DoesNotExistHandle(req: Request, exc: Exception) -> JSONResponse:
    return await BaseHandle(
        req,
        exc,
        DoesNotExist,
        404,
        f"Object has not found, exc: {exc}, path: {req.path_params}, query: {req.query_params}",
        404,
    )


async def IntegrityHandle(req: Request, exc: Exception) -> JSONResponse:
    return await BaseHandle(
        req, exc, IntegrityError, 500, f"IntegrityError，{exc}, path: {req.path_params}, query: {req.query_params}", 500
    )


async def HttpExcHandle(req: Request, exc: HTTPException) -> JSONResponse:
    # 尝试将错误码转换为 HTTP 状态码，如果不是有效的 HTTP 状态码，则默认返回 400 Bad Request
    status_code = 400
    if isinstance(exc.code, int):
        status_code = exc.code
    elif isinstance(exc.code, str) and exc.code.isdigit():
        status_code = int(exc.code)

    # 确保状态码在有效范围内 (100-599)
    if not (100 <= status_code <= 599):
        status_code = 400

    return await BaseHandle(req, exc, HTTPException, exc.code, exc.msg, status_code)


async def RequestValidationHandle(req: Request, exc: RequestValidationError) -> JSONResponse:
    return await BaseHandle(req, exc, RequestValidationError, 422, "RequestValidationError", status_code=422, detail=exc.errors())


async def ResponseValidationHandle(req: Request, exc: ResponseValidationError) -> JSONResponse:
    return await BaseHandle(req, exc, ResponseValidationError, 422, "ResponseValidationError", status_code=422, detail=exc.errors())
