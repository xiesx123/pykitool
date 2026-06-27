import os
import sys

sys.path.insert(0, os.getcwd())

from enum import IntEnum
from typing import Any, Generic, TypeVar

from loguru import logger
from pydantic import BaseModel

MAX_LOG_LENGTH = 500
LIST_PREVIEW = 3
DICT_PREVIEW = 5

T = TypeVar("T")


# 响应码类型
class ResponseCode(IntEnum):
    SUCCESS = 0  # 成功
    FAILURE = 1  # 失败
    ERROR = -1  # 错误


# 通用响应模型
class ResponseModel(BaseModel, Generic[T]):
    code: int
    message: str
    data: T

    # 将数据转换为 JSON 字符串，并对列表或字典进行预览截断
    @staticmethod
    def _json_preview(data: Any, max_length: int = MAX_LOG_LENGTH) -> str:
        from pykitool.utils import cbutils

        try:
            if isinstance(data, dict):
                preview_dict = dict(list(data.items())[:DICT_PREVIEW])
                json_str = cbutils.to_json(preview_dict)
            elif isinstance(data, list):
                preview_list = data[:LIST_PREVIEW]
                json_str = cbutils.to_json(preview_list)
            else:
                json_str = str(data)

            # 全局截断
            if len(json_str) > max_length:
                json_str = json_str[:max_length] + " ... [truncated]"

            return json_str
        except Exception as e:
            return f"<Failed to serialize data: {e}>"

    @staticmethod
    def success(code: int = 0, message: str = "success", data: Any = {}) -> "ResponseModel":
        response = ResponseModel(code=code, message=message, data=data)
        if data is not {}:
            logger.info(response._json_preview(data))
        return response

    @staticmethod
    def failure(code: int = 1, message: str = "failure", data: Any = {}) -> "ResponseModel":
        response = ResponseModel(code=code, message=message, data=data)
        if data is not {}:
            logger.info(response._json_preview(data))
        return response

    @staticmethod
    def error(code: int = -1, message: str = "error", data: Any = {}) -> "ResponseModel":
        response = ResponseModel(code=code, message=message, data=data)
        if data is not {}:
            logger.info(response._json_preview(data))
        return response


# 通用分页响应模型
class ResponsePageModel(BaseModel, Generic[T]):
    code: int = 0
    msg: str = ""
    count: int = 0
    data: list[T] = []
