import time
from typing import Optional

from fastapi import FastAPI, Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from pykitool.utils import cbjson


class LoggingAdvice(BaseHTTPMiddleware):
    """
    FastAPI 全局拦截器，类似 Spring Boot @RestControllerAdvice。

    功能：
    - 自动打印请求/响应日志（method、path、query params、body、耗时、状态码、响应预览）
    - 支持 include_paths 仅拦截指定路径前缀，未匹配的请求跳过日志拦截直接透传
    - 支持 exclude_paths 排除指定路径前缀，跳过日志拦截
    - 配合 register_controller_advice() 使用，统一捕获异常并返回 R.error() 格式

    示例::

        from fastapi import FastAPI
        from pykitool.core.advice import register_controller_advice

        app = FastAPI()
        register_controller_advice(app, include_paths=["/api"], exclude_paths=["/health", "/docs", "/openapi.json"])
    """

    def __init__(self, app, include_paths: Optional[list] = None, exclude_paths: Optional[list] = None):
        """
        :param app:           ASGI app（由 FastAPI 自动传入，无需手动传）
        :param include_paths: 可选，仅拦截路径前缀列表，非空时只有匹配的请求才打印日志，未匹配的直接透传。
                              例如：``["/api"]``
        :param exclude_paths: 可选，排除路径前缀列表，匹配到的请求跳过日志拦截直接透传。
                              例如：``["/health", "/docs", "/openapi.json"]``
        """
        super().__init__(app)
        self._include_paths = include_paths or []
        self._exclude_paths = exclude_paths or []

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # 排除路径，直接透传，不打印日志
        if any(path.startswith(p) for p in self._exclude_paths):
            return await call_next(request)

        # 包含路径，非空时仅拦截匹配的路径，未匹配直接透传
        if self._include_paths and not any(path.startswith(p) for p in self._include_paths):
            return await call_next(request)

        start = time.perf_counter()
        request.state.start_time = start

        method = request.method
        params = dict(request.query_params)

        # 读取 body —— Starlette 会将结果缓存到 request._body，
        # 后续 route handler 调用 request.body() / request.json() 仍可正常读取，不会二次消费流。
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""

        parts = [f"{method} {path}"]
        if params:
            parts.append(f"params={str(params)}")
        if body_str:
            parts.append(f"body={body_str}")
        logger.info(" ".join(parts))

        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"{method} {path} {response.status_code} {elapsed:.2f}ms")

        # 消费流式 body，重建 Response，防止客户端收不到数据
        body_chunks = [chunk async for chunk in response.body_iterator]
        body_bytes_out = b"".join(body_chunks)
        response = Response(
            content=body_bytes_out,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        logger.info(f"{cbjson.preview_json(body_bytes_out.decode('utf-8', errors='replace'))}")
        return response


def register_controller_advice(
    app: FastAPI,
    include_paths: Optional[list] = None,
    exclude_paths: Optional[list] = None,
) -> None:
    """
    注册统一返回处理器

    示例::

        from fastapi import FastAPI
        from pykitool.core.advice import register_controller_advice

        app = FastAPI()

        # 不排除任何路径
        register_controller_advice(app)

        # 仅拦截 /api 前缀路径
        register_controller_advice(app, include_paths=["/api"])

        # 排除健康检查和文档路径
        register_controller_advice(app, exclude_paths=["/health", "/docs", "/openapi.json"])

        # 组合使用：仅拦截 /api，同时排除 /api/internal
        register_controller_advice(app, include_paths=["/api"], exclude_paths=["/api/internal"])
    """
    app.add_middleware(LoggingAdvice, include_paths=include_paths, exclude_paths=exclude_paths)
