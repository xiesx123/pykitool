import json
from pathlib import Path
from typing import Any, Union

from hutool import JSONUtil, PathUtil
from loguru import logger

from pykitool.utils import cbfile, cbjson


# 验证字符串是否为有效的 JSON 格式
def is_json(data: str) -> bool:
    return JSONUtil.is_json(data)


# 解析 JSON 字符串
def load_json(data: str, default: Any = None) -> Any:
    try:
        return JSONUtil.parse(data)
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse JSON: {str(e)}")
        return default


# 从文件加载 JSON 数据
def load_json_file(path: Union[str, Path], default: Any = None) -> Any:
    try:
        if not cbfile.exist(path):
            return default
        return JSONUtil.read_json(path=path)
    except (ValueError, IOError, OSError) as e:
        logger.error(f"Failed to load JSON file {path}: {str(e)}")
        return default


# 将数据转换为 JSON 字符串（紧凑格式）
def to_json(data: Any) -> str:
    return JSONUtil.to_json_str(data)


# 将数据转换为格式化的 JSON 字符串
def to_json_pretty(data: Any, indent: int = 2, sort: bool = False) -> str:
    if not sort:
        return JSONUtil.to_json_pretty_str(data)
    return json.dumps(
        data,
        ensure_ascii=False,
        default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
        indent=indent,
        sort_keys=sort,
    )


# 对预览数据截断
def preview_json(data: Any, max_length: int = 500, dict_size: int = 5, list_size: int = 5) -> str:
    try:
        if isinstance(data, dict):
            preview_dict = dict(list(data.items())[:dict_size])
            json_str = cbjson.to_json(preview_dict)
        elif isinstance(data, list):
            preview_list = data[:list_size]
            json_str = cbjson.to_json(preview_list)
        else:
            json_str = str(data)

        # 全局截断
        if len(json_str) > max_length:
            json_str = json_str[:max_length] + " ... [truncated]"

        return json_str
    except Exception as e:
        return f"Failed to serialize data: {e}>"


# ================================ 调用示例 ================================

if __name__ == "__main__":

    data = {"name": "张三", "age": 30, "city": "北京"}
    output = PathUtil.create_temp_file(prefix="test", suffix=".json")
    print(output)

    # 验证字符串是否为有效的 JSON 格式
    print(is_json(cbjson.to_json_pretty(data)))

    # 解析 JSON 字符串
    print(load_json(cbjson.to_json_pretty(data)))

    # 从文件加载 JSON 数据
    print(load_json_file(cbfile.write(output, cbjson.to_json_pretty(data)), default={}))

    # 将数据转换为 JSON 字符串（紧凑格式）
    print(to_json(data))

    # 将数据转换为格式化的 JSON 字符串
    print(to_json_pretty(data))
    print(to_json_pretty(data, indent=2, sort=True))
