import time
from enum import Enum

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from pykitool.base.enums import AbstractEnum
from pykitool.base.result import R
from pykitool.support.firebase.exceptions import FirebaseException


# 异常基码
class ExcCode(AbstractEnum, Enum):

    RUNTIME = (1000, "Runtime Error")

    ASYNC = (1010, "Execution Error")

    REQUEST = (2000, "Request Failed")

    RETRY = (2010, "Retry Failed")

    LIMITER = (2020, "Request Rate Limited")

    VALIDATOR = (3000, "Validation Error")

    DBASE = (4000, "Database Error")

    TOKEN = (5000, "Token Error")

    SIGN = (6000, "Signature Error")

    UNKNOWN = (9999, "Unknown")

    def __new__(cls, value: int, label: str):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.label = label
        return obj


# 异常基类
class RuntimeException(Exception):
    def __init__(self, message: str, code: int = -1):
        self.status_code = code
        self.message = message
        super().__init__(self.message)


# 异常拦截
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.exception(f"<! {request.method} {request.url.path}  Exception: {exc}{elapsed} >")
    return JSONResponse(content=R.error(message=str(exc)).model_dump(), status_code=500)


async def firebase_exception_handler(request: Request, exc: FirebaseException) -> JSONResponse:
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.warning(f"<! {request.method} {request.url.path}  FirebaseException: {exc.message}{elapsed} >")
    return JSONResponse(content=R.error(message=exc.message).model_dump())


async def runtime_exception_handler(request: Request, exc: RuntimeException) -> JSONResponse:
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.warning(f"<! {request.method} {request.url.path}  RuntimeException: {exc.message} (code={exc.status_code}){elapsed} >")
    return JSONResponse(content=R.error(code=exc.status_code, message=exc.message).model_dump())


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
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(FirebaseException, firebase_exception_handler)
    app.add_exception_handler(RuntimeException, runtime_exception_handler)
