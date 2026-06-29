import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from pykitool.base.result import R


# 异常基类
class RuntimeException(Exception):
    def __init__(self, message: str, code: int = -1):
        self.status_code = code
        self.message = message
        super().__init__(self.message)


# 异常拦截
async def runtime_exception_handler(request: Request, exc: RuntimeException) -> JSONResponse:
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.warning(f"<!  {request.method} {request.url.path}  RuntimeException: {exc.message} (code={exc.status_code}){elapsed}")
    return JSONResponse(content=R.error(code=exc.status_code, message=exc.message).model_dump())


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.exception(f"<!  {request.method} {request.url.path}  Exception: {exc}{elapsed}")
    return JSONResponse(content=R.error(message=str(exc)).model_dump(), status_code=500)


def register_controller_exception(
    app: FastAPI,
) -> None:
    """
    注册全局异常处理器

    用法::

        from fastapi import FastAPI
        from pykitool.core.advice import register_controller_advice
        app = FastAPI()
        register_controller_exception(app)
    """
    app.add_exception_handler(RuntimeException, runtime_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
