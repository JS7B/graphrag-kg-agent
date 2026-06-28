"""统一错误响应结构与全局异常处理器。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 通用 500 文案：不向客户端泄露内部细节（路径/库版本/堆栈），详情仅写日志。
_INTERNAL_ERROR_MESSAGE = "服务内部错误，请稍后重试"


class ErrorDetail(BaseModel):
    type: str
    message: str


class ErrorResponse(BaseModel):
    """统一错误响应：{"error": {"type": ..., "message": ...}}"""

    error: ErrorDetail


def _payload(type_: str, message: str) -> dict:
    return ErrorResponse(error=ErrorDetail(type=type_, message=message)).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，保证所有错误返回统一结构。"""

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        # 详情写日志便于排查，但返回固定文案避免泄露内部实现（路径/库版本等）
        logger.exception("未处理异常")
        return JSONResponse(
            status_code=500,
            content=_payload("internal_error", _INTERNAL_ERROR_MESSAGE),
        )
