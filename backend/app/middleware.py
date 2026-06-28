"""轻量鉴权中间件：校验 X-API-Key header，为公开仓库防裸 curl 删库/耗 token/读图谱。

设计取舍（个人项目，简单优先）：
- API_KEY 为空时跳过校验——本地开发无需配 key 也能跑，部署时在 .env 填真实值即启用。
- 仅 /health 豯免（探针不能被鉴权挡住），其余接口一律校验。
- 用 BaseHTTPMiddleware 而非纯 ASGI，代码量小、可读；个人单用户场景性能非瓶颈。
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings

# 健康检查路径前缀：探针豁免鉴权，否则部署后没法用它探活。
_HEALTH_PREFIX = "/health"


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """校验请求头 X-API-Key。settings.api_key 为空则放行（开发模式）。"""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        # 未配置 API_KEY → 开发模式，直接放行
        if not settings.api_key:
            return await call_next(request)
        # /health 豯免：探针不能被鉴权挡住
        if request.url.path.startswith(_HEALTH_PREFIX):
            return await call_next(request)
        # 校验 header
        if request.headers.get("X-API-Key") != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"error": {"type": "unauthorized", "message": "无效或缺失的 API Key"}},
            )
        return await call_next(request)
