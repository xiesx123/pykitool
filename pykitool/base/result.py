from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field
from typing_extensions import overload

from pykitool.base.enums import AbstractEnum

T = TypeVar("T")


# 状态码
class StatusCode(AbstractEnum, Enum):
    SUCCESS = (0, "success")
    FAILURE = (1, "failure")
    ERROR = (-1, "error")

    def __new__(cls, value: int, label: str):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.label = label
        return obj


# 基类
class BaseResult(BaseModel):
    code: int = Field(default=0, description="状态")
    message: str = Field(default="", description="消息")

    def is_success(self) -> bool:
        return self.code == StatusCode.SUCCESS.value

    def is_fail(self) -> bool:
        return self.code == StatusCode.FAILURE.value

    def is_error(self) -> bool:
        return self.code == StatusCode.ERROR.value


# ================================ 默认 ================================


# 返回结果
class Result(BaseResult, Generic[T]):
    data: T = Field(default=None, description="数据")


# 构造 Result
class R:

    # success()
    @overload
    @classmethod
    def success(cls) -> Result: ...

    # success(code, message)
    @overload
    @classmethod
    def success(cls, code: int, message: str) -> Result: ...

    # success(code, message, data)
    @overload
    @classmethod
    def success(cls, code: int, message: str, data: Any) -> Result: ...

    @classmethod
    def success(cls, code: int = StatusCode.SUCCESS.value, message: str = StatusCode.SUCCESS.label, data: Any = {}) -> Result:
        return Result(code=code, message=message, data=data)

    # failure()
    @overload
    @classmethod
    def failure(cls) -> Result: ...

    # failure(code, message)
    @overload
    @classmethod
    def failure(cls, code: int, message: str) -> Result: ...

    # failure(code, message, data)
    @overload
    @classmethod
    def failure(cls, code: int, message: str, data: Any) -> Result: ...

    @classmethod
    def failure(cls, code: int = StatusCode.FAILURE.value, message: str = StatusCode.FAILURE.label, data: Any = {}) -> Result:
        return Result(code=code, message=message, data=data)

    # error()
    @overload
    @classmethod
    def error(cls) -> Result: ...

    # error(code, message)
    @overload
    @classmethod
    def error(cls, code: int, message: str) -> Result: ...

    # error(code, message, data)
    @overload
    @classmethod
    def error(cls, code: int, message: str, data: Any) -> Result: ...

    @classmethod
    def error(cls, code: int = StatusCode.ERROR.value, message: str = StatusCode.ERROR.label, data: Any = {}) -> Result:
        return Result(code=code, message=message, data=data)


# ================================ 分页 ================================


# 分页结果
class PResult(BaseResult, Generic[T]):
    data: list[T] = Field(default_factory=list, description="数据")
    count: int = Field(default=0, description="总数")


# 构造 PResult
class PR:

    # success()
    @overload
    @classmethod
    def success(cls) -> PResult: ...

    # success(code, message)
    @overload
    @classmethod
    def success(cls, code: int, message: str) -> PResult: ...

    # success(code, message, data)
    @overload
    @classmethod
    def success(cls, code: int, message: str, data: list, count: int) -> PResult: ...

    @classmethod
    def success(cls, code: int = StatusCode.SUCCESS.value, message: str = StatusCode.SUCCESS.label, data: list = [], count: int = 0) -> PResult:
        return PResult(code=code, message=message, data=data, count=count)

    # failure()
    @overload
    @classmethod
    def failure(cls) -> PResult: ...

    # failure(code, message)
    @overload
    @classmethod
    def failure(cls, code: int, message: str) -> PResult: ...

    # failure(code, message, data)
    @overload
    @classmethod
    def failure(cls, code: int, message: str, data: list, count: int) -> PResult: ...

    @classmethod
    def failure(cls, code: int = StatusCode.FAILURE.value, message: str = StatusCode.FAILURE.label, data: list = [], count: int = 0) -> PResult:
        return PResult(code=code, message=message, data=data, count=count)

    # error()
    @overload
    @classmethod
    def error(cls) -> PResult: ...

    # error(code, message)
    @overload
    @classmethod
    def error(cls, code: int, message: str) -> PResult: ...

    # error(code, message, data)
    @overload
    @classmethod
    def error(cls, code: int, message: str, data: list, count: int) -> PResult: ...

    @classmethod
    def error(cls, code: int = StatusCode.ERROR.value, message: str = StatusCode.ERROR.label, data: list = [], count: int = 0) -> PResult:
        return PResult(code=code, message=message, data=data, count=count)
