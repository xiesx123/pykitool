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
    """
    业务异常码枚举，每个枚举项包含数字码和说明文字。

    枚举项::

        RUNTIME   (1000) - 运行时错误
        ASYNC     (1010) - 异步执行错误
        REQUEST   (2000) - 请求失败
        RETRY     (2010) - 重试失败
        LIMITER   (2020) - 请求限流
        VALIDATOR (3000) - 参数校验错误
        DBASE     (4000) - 数据库错误
        TOKEN     (5000) - Token 错误
        SIGN      (6000) - 签名错误
        UNKNOWN   (9999) - 未知错误

    示例::

        from pykitool.controller.exception import ExcCode, RuntimeException

        raise RuntimeException(message=ExcCode.TOKEN.label, code=ExcCode.TOKEN.value)
    """

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
    """
    通用运行时异常，可携带自定义错误码和消息，配合全局异常处理器自动转为 JSON 响应。

    Args:
        message: 错误消息
        code:    业务错误码，默认 -1；可传入 ExcCode.value 枚举值

    示例::

        from pykitool.controller.exception import ExcCode, RuntimeException

        # 直接抛出
        raise RuntimeException(message="操作失败")

        # 携带业务码
        raise RuntimeException(message="Token 已过期", code=ExcCode.TOKEN.value)

        # 在路由处理函数中使用
        def my_handler():
            if not ok:
                raise RuntimeException(message="参数错误", code=ExcCode.VALIDATOR.value)
    """

    def __init__(self, message: str, code: int = -1):
        self.status_code = code
        self.message = message
        super().__init__(self.message)


# 异常拦截
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局兜底异常处理器，捕获所有未被其他处理器拦截的异常。

    - 记录完整堆栈日志（logger.exception）
    - 返回 HTTP 500，body 为 ``R.error(message=...)`` 格式
    """
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.exception(f"<! {request.method} {request.url.path}  Exception: {exc}{elapsed} >")
    return JSONResponse(content=R.error(message=str(exc)).model_dump(), status_code=500)


async def firebase_exception_handler(request: Request, exc: FirebaseException) -> JSONResponse:
    """
    Firebase 异常处理器，捕获 ``FirebaseException``。

    - 记录 warning 日志
    - 返回 HTTP 200，body 为 ``R.error(message=exc.message)`` 格式
    """
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.warning(f"<! {request.method} {request.url.path}  FirebaseException: {exc.message}{elapsed} >")
    return JSONResponse(content=R.error(message=exc.message).model_dump())


async def runtime_exception_handler(request: Request, exc: RuntimeException) -> JSONResponse:
    """
    RuntimeException 处理器，捕获业务层主动抛出的 ``RuntimeException``。

    - 记录 warning 日志（含业务码与耗时）
    - 返回 HTTP 200，body 为 ``R.error(code=exc.status_code, message=exc.message)`` 格式
    """
    start = getattr(request.state, "start_time", None)
    elapsed = f"  {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.warning(f"<! {request.method} {request.url.path}  RuntimeException: {exc.message} (code={exc.status_code}){elapsed} >")
    return JSONResponse(content=R.error(code=exc.status_code, message=exc.message).model_dump())


def register_controller_exception(
    app: FastAPI,
) -> None:
    """
    注册全局异常处理器，统一将异常转换为 ``R.error()`` JSON 响应格式。

    注册的处理器优先级（从高到低）：

    1. ``RuntimeException``  → ``runtime_exception_handler``  (业务异常，HTTP 200)
    2. ``FirebaseException`` → ``firebase_exception_handler`` (Firebase 异常，HTTP 200)
    3. ``Exception``         → ``global_exception_handler``   (兜底，HTTP 500)

    Args:
        app: FastAPI 实例

    示例::

        from fastapi import FastAPI
        from pykitool.controller.exception import register_controller_exception

        app = FastAPI()
        register_controller_exception(app)

        # 通常与 register_controller_advice 配合使用
        from pykitool.controller.advice import register_controller_advice

        register_controller_advice(app, exclude_paths=["/health", "/docs"])
        register_controller_exception(app)
    """
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(FirebaseException, firebase_exception_handler)
    app.add_exception_handler(RuntimeException, runtime_exception_handler)
