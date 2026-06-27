import base64
import hashlib
import json
import os
import platform
import random
import re
import secrets
import string
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from pykitool.base.enums import Platform
from pykitool.utils import cbruntime

# 预编译正则表达式（模块级别）
_HTTP_PATTERN = re.compile(r"^https?://")
_NUMBER_PATTERN = re.compile(r"(\d+)")

# 获取随机 User-Agent
_ua_instance = None

# ================================ Common 通用功能 ================================


# 判断是否为调试模式
def is_debug() -> bool:
    return cbruntime.get_arg(["--reload", "--debug"], False)


# 判断是否为 HTTP/HTTPS 链接
def is_http(url: str) -> bool:
    if not url:
        return False
    return _HTTP_PATTERN.match(url) is not None


# ================================ Device 设备信息 ================================


# 判断是否为 Windows 系统
def is_windows() -> bool:
    return platform.system().lower() == Platform.Window.value


# 判断是否为 Linux 系统
def is_linux() -> bool:
    return platform.system().lower() == Platform.Linux.value


# 判断是否为 Mac 系统
def is_mac() -> bool:
    return platform.system().lower() == Platform.Mac.value


# 生成指定范围内的随机数
def get_random(start: int = 10000000, end: int = 99999999) -> int:
    return random.randint(start, end)


# ================================ Git 版本信息 ================================


def get_git_info():

    git_info = {"branch": "unknown", "date": "unknown", "hash": "unknown"}

    try:
        repo_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        # 获取分支名
        result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            git_info["branch"] = result.stdout.strip()

        # 获取最后提交时间
        result = subprocess.run(["git", "log", "-1", "--format=%ci"], cwd=repo_path, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            git_info["date"] = result.stdout.strip()

        # 获取短 commit hash
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_path, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            git_info["hash"] = result.stdout.strip()
    except Exception as e:
        print(f"Warning: Failed to get git info - {e}")

    return git_info


# ================================ Json 数据操作 ================================


# 验证字符串是否为有效的 JSON 格式
def is_json(data: str) -> bool:
    if not data or not isinstance(data, str):
        return False
    # 快速检查：JSON 必须以 {、[ 开头或是基本类型
    data_stripped = data.strip()
    if not data_stripped:
        return False
    first_char = data_stripped[0]
    if first_char not in ("{", "[", '"', "t", "f", "n", "-", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
        return False
    try:
        json.loads(data)
        return True
    except (ValueError, TypeError):
        return False


# 解析 JSON 字符串
def load_json(data: str, default: Any = None) -> Any:
    try:
        return json.loads(data)
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse JSON: {str(e)}")
        return default


# 从文件加载 JSON 数据
def load_json_file(path: Union[str, Path], default: Any = None) -> Any:
    try:
        path_obj = Path(path) if isinstance(path, str) else path
        if not path_obj.exists():
            return default
        with open(path_obj, "r", encoding="utf-8") as file:
            return json.load(file)
    except (ValueError, IOError, OSError) as e:
        logger.error(f"Failed to load JSON file {path}: {str(e)}")
        return default


# 将数据转换为 JSON 字符串（紧凑格式）
def to_json(data: Any) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
        default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
    )


# 将数据转换为格式化的 JSON 字符串
def to_json_pretty(data: Any, indent: int = 4, sort_keys: bool = False) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
        indent=indent,
        sort_keys=sort_keys,
    )


# ================================ Encrypt 加密解密 ================================


# 加密数据
def encrypt(data: Any, password: str = "0123456789") -> Optional[str]:
    try:
        raw = json.dumps(data).encode("utf-8")
        key = hashlib.sha256(password.encode()).digest()
        encrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(raw)])
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption failed: {str(e)}")
        return None


# 解密数据
def decrypt(enc_data: str, password: str = "0123456789") -> Any:
    try:
        encrypted = base64.b64decode(enc_data)
        key = hashlib.sha256(password.encode()).digest()
        decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(encrypted)])
        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}")
        return None


# ================================ String 字符串操作 ================================


# 生成终端超链接
def str_hyperlink(url: str, text: str) -> str:
    ESC = "\033"
    return f"{ESC}]8;;{url}{ESC}\\{text}{ESC}]8;;{ESC}\\"


# 生成随机密码
def str_password(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits  # 字母+数字
    while True:
        password = "".join(secrets.choice(chars) for _ in range(length))
        # 确保至少包含一个字母和一个数字
        if any(c.isdigit() for c in password) and any(c.isalpha() for c in password):
            return password


# 计算字符串的 MD5 哈希值
def str_to_md5(text: str) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(text.encode("utf-8"))
    return md5_hash.hexdigest()


# 计算字符串的 MD5 哈希值（截取指定位数）
def str_to_md5_short(text: str, length: int = 6) -> str:
    return str_to_md5(text)[:length]


# 生成 UUID 字符串（无连字符）
def uuid_str() -> str:
    return str(uuid.uuid4()).replace("-", "")


# 生成数字型 UUID（时间戳+随机数）
def uuid_numeric() -> str:
    return str(int(time.time() * 1000)) + str(random.randint(1000, 9999))


# 生成随机 User-Agent
def random_ua() -> str:
    global _ua_instance
    if _ua_instance is None:
        from fake_useragent import UserAgent

        _ua_instance = UserAgent()
    return _ua_instance.random


# 生成指定范围内的随机数
def random_int(start: int = 10000000, end: int = 99999999) -> int:
    return random.randint(start, end)


# ================================ Time 时间操作 ================================


# 获取当前时间
def get_current_time(format: str = "%Y-%m-%d %H:%M:%S", as_string: bool = True) -> Union[str, datetime]:
    now = datetime.now()
    if as_string:
        return now.strftime(format)
    return now


# 将时间戳格式化为本地时间字符串
def format_to_localtime(ts: Union[int, float] = 0, format: str = "%Y-%m-%d %H:%M:%S") -> Union[str, int]:
    try:
        if ts == 0:
            return "Never"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception as e:
        logger.error(f"Format to localtime failed: {str(e)}")
        return 0


# 计算距离指定时间的剩余天数
def time_interval_days(end_time: str, now_time: Optional[str] = None, use_http: bool = False, url: str = "https://www.baidu.com") -> int:
    fmt = "%Y-%m-%d %H:%M:%S"
    end_dt = datetime.strptime(end_time, fmt)

    if now_time:
        now_dt = datetime.strptime(now_time, fmt)
    else:
        now_dt = datetime.now()

    delta = end_dt - now_dt
    return delta.days if delta.days >= 0 else -1


# 将 cron 表达式的小时字段从 CST（东八区）转换为 UTC（-8h），仅处理固定数字小时
def cst_to_utc(expr: str) -> str:
    parts = expr.strip().split()
    if len(parts) != 5:
        return expr
    minute, hour, day, month, weekday = parts
    if hour.isdigit():
        utc_hour = (int(hour) - 8) % 24
        return " ".join([minute, str(utc_hour), day, month, weekday])
    return expr


# ================================ List 列表操作 ================================


# 根据字段值查找列表中的元素
def find_list_item_by_field(items: List[Union[Dict[str, Any], Any]], field: str, value: Any) -> Optional[Union[Dict[str, Any], Any]]:
    for item in items:
        if isinstance(item, dict):
            if item.get(field) == value:
                return item
        else:
            if getattr(item, field, None) == value:
                return item
    return None


# 查找字段值在指定集合中的所有元素
def find_list_item_by_value_in_set(array: List[Dict[str, Any]], field: str, values_set: set) -> List[Dict[str, Any]]:
    return [item for item in array if item.get(field) in values_set]


# 对字符串列表排序（数字优先，字母其次）
def sort_by_array(items: List[str]) -> List[str]:
    def sort_key(x: str) -> tuple[Union[int, float], str]:
        match = _NUMBER_PATTERN.match(x)
        num = int(match.group(1)) if match else float("inf")
        return (num, x.lower())

    return sorted(items, key=sort_key)


# 对字典按键排序（数字优先，字母其次）
def sort_by_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    def sort_key(k: str) -> tuple[Union[int, float], str]:
        match = _NUMBER_PATTERN.match(k)
        num = int(match.group(1)) if match else float("inf")
        return (num, k.lower())

    sorted_items = sorted(d.items(), key=lambda item: sort_key(item[0]))
    return dict(sorted_items)


# ================================ 调用示例 ================================

if __name__ == "__main__":

    # ==================== Common 通用功能示例 ====================

    # 判断是否为调试模式
    # result = is_debug()
    # logger.info(f"Is debug mode: {result}")

    # 判断是否为 HTTP/HTTPS 链接
    # result = is_http("https://example.com")
    # logger.info(f"Is HTTP URL: {result}")

    # ==================== Network 网络与语言示例 ====================

    # 获取系统语言环境
    # result = get_locale()
    # logger.info(f"System locale: {result}")

    # 根据语言代码获取完整的语言环境标识
    # result = get_locale_by_lang("zh", "zh-CN")
    # logger.info(f"Locale by lang: {result}")

    # 解析语言标签，返回语言和地区
    # lang, region = parse_locale("zh-CN")
    # logger.info(f"Parse locale: lang={lang}, region={region}")

    # 检测文本的语言类型
    # result = detect_language("Hello World")
    # logger.info(f"Detect language: {result}")

    # 智能拼接文本（根据语言决定是否添加空格）
    # result = smart_join(["Hello", "World"])
    # logger.info(f"Smart join: {result}")

    # ==================== Device 设备信息示例 ====================

    # 判断操作系统类型
    # logger.info(f"Is Windows: {is_windows()}")
    # logger.info(f"Is Linux: {is_linux()}")
    # logger.info(f"Is Mac: {is_mac()}")

    # 生成指定范围内的随机数
    # result = get_random(1, 100)
    # logger.info(f"Random number: {result}")

    # 设置随机种子，确保结果可复现
    # seed = set_random_seed(42)
    # logger.info(f"Set random seed: {seed}")

    # 获取可用的 CPU 核心数
    # count = cpu_available_count()
    # logger.info(f"Available CPU count: {count}")

    # 判断 CUDA 是否可用
    # result = cuda_is_available()
    # logger.info(f"CUDA available: {result}")

    # 清空 CUDA 显存缓存
    # cuda_memory_clear()
    # logger.info("CUDA memory cleared")

    # 获取计算设备（CPU 或 GPU）
    # result = device()
    # logger.info(f"Device: {result}")

    # ==================== Json JSON操作示例 ====================

    # 验证字符串是否为有效的 JSON 格式
    # result = is_json('{"key": "value"}')
    # logger.info(f"Is JSON: {result}")

    # 解析 JSON 字符串
    # result = load_json('{"key": "value"}')
    # logger.info(f"Load JSON: {result}")

    # 从文件加载 JSON 数据
    # result = load_json_file("config.json", default={})
    # logger.info(f"Load JSON file: {result}")

    # 将数据转换为 JSON 字符串（紧凑格式）
    # data = {"name": "张三", "age": 30, "city": "北京"}
    # result = to_json(data)
    # logger.info(f"To JSON: {result}")

    # 将数据转换为格式化的 JSON 字符串
    # result = to_json_pretty(data, indent=2)
    # logger.info(f"To JSON pretty:\n{result}")

    # ==================== Encrypt 加密解密示例 ====================

    # 加密和解密数据
    # original_data = {"username": "admin", "password": "123456"}
    # encrypted = encrypt(original_data)
    # logger.info(f"Encrypted: {encrypted}")
    # decrypted = decrypt(encrypted)
    # logger.info(f"Decrypted: {decrypted}")

    # ==================== String 字符串操作示例 ====================

    # 生成终端超链接
    # result = str_hyperlink("https://github.com", "GitHub")
    # logger.info(f"Hyperlink: {result}")

    # 生成随机密码
    # result = str_password(8)
    # logger.info(f"Random password: {result}")

    # 计算字符串的 MD5 哈希值
    # result = str_to_md5("Hello World")
    # logger.info(f"MD5: {result}")

    # 计算字符串的 MD5 哈希值（截取指定位数）
    # result = str_to_md5_short("Hello World", 8)
    # logger.info(f"MD5 short: {result}")

    # 生成 UUID 字符串
    # result = uuid_str()
    # logger.info(f"UUID string: {result}")

    # 生成数字型 UUID
    # result = uuid_numeric()
    # logger.info(f"UUID numeric: {result}")

    # 生成随机 User-Agent
    # result = random_ua()
    # logger.info(f"Random UA: {result}")

    # ==================== Time 时间操作示例 ====================

    # 获取当前时间
    # result = get_current_time()
    # logger.info(f"Current time: {result}")

    # 获取当前时间（datetime 对象）
    # result = get_current_time(as_string=False)
    # logger.info(f"Current time (datetime): {result}")

    # 通过 HTTP 请求获取网络时间
    # result = get_http_time()
    # logger.info(f"HTTP time: {result}")

    # 将时间戳格式化为本地时间字符串
    # result = format_to_localtime(1704067200)
    # logger.info(f"Format timestamp: {result}")

    # 格式化为 SRT 字幕时间格式
    # result = format_to_srttime(125.5, "s")
    # logger.info(f"SRT time: {result}")

    # 将 SRT 时间格式转换为秒数
    # result = time_to_ss("00:00:14,420")
    # logger.info(f"SRT to seconds: {result}")

    # 将 SRT 时间格式转换为毫秒数
    # result = time_to_ms("00:00:14,420")
    # logger.info(f"SRT to milliseconds: {result}")

    # 计算距离指定时间的剩余天数
    # end_time = "2025-12-31 23:59:59"
    # result = time_interval_days(end_time)
    # logger.info(f"Days until end: {result}")

    # ==================== List 列表操作示例 ====================

    # 根据字段值查找列表中的元素
    # items = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    # result = find_list_item_by_field(items, "id", 2)
    # logger.info(f"Find by field: {result}")

    # 查找字段值在指定集合中的所有元素
    # result = find_list_item_by_value_in_set(items, "id", {1, 3})
    # logger.info(f"Find by value in set: {result}")

    # 对字符串列表排序（数字优先，字母其次）
    # arr = ["item10", "item2", "item1", "itemA", "item20"]
    # result = sort_by_array(arr)
    # logger.info(f"Sort array: {result}")

    # 对字典按键排序（数字优先，字母其次）
    # d = {"key10": "v10", "key2": "v2", "key1": "v1", "keyA": "vA"}
    # result = sort_by_dict(d)
    # logger.info(f"Sort dict: {result}")

    pass
