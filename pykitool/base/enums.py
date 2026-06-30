import platform
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar

from loguru import logger

E = TypeVar("E", bound=Enum)
F = TypeVar("F", bound=Callable[..., Any])


# 基类
class AbstractEnum:

    @classmethod
    def from_value(cls: Type[E], val: str) -> E:
        for member in cls:
            if member.value == val:
                return member
        return None

    @classmethod
    def from_name(cls: Type[E], name: str) -> E:
        try:
            return cls[name]
        except KeyError:
            return None

    @classmethod
    def choices(cls):
        return [(member.name, member.value) for member in cls]

    @classmethod
    def names(cls):
        return [member.name for member in cls]

    @classmethod
    def values(cls):
        return [member.value for member in cls]

    @classmethod
    def has_name(cls, name):
        return name in cls.__members__

    @classmethod
    def has_value(cls, val):
        return val in cls._value2member_map_


# 基础
class BaseAbstractEnum:

    # 代理
    class Protocol(AbstractEnum, Enum):
        HTTP = "http"
        SOCKS5 = "socks5"


# 平台
class Platform(AbstractEnum, Enum):
    Window = "windows"
    Linux = "linux"
    Mac = "darwin"

    # 指定平台装饰器，限制函数只在特定操作系统上执行
    def system(*valid_os, enabled: bool = True) -> Callable[[F], F]:

        # 装饰器
        def decorator(func: F) -> F:

            @wraps(func)
            def wrapper(*args, **kwargs) -> Optional[Any]:
                # 获取当前操作系统名称并转为小写
                current_os = platform.system().lower()
                # 转换 valid_os 为小写列表
                os_list = [os_name.value for os_name in valid_os]
                # 如果当前操作系统符合要求，执行函数
                if current_os in os_list:
                    return func(*args, **kwargs)
                else:
                    if enabled:
                        logger.debug(f"Function {func.__name__} is not supported on {platform.system()}. Skipping.")
                    return None

            return wrapper

        return decorator


if __name__ == "__main__":
    print(Platform.from_name(Platform.Window.name))
    print(Platform.from_value("windows"))
    print(Platform.choices())
    print(Platform.names())
    print(Platform.values())
    print(Platform.has_value("windows"))
    print(Platform.has_value("windows2"))
