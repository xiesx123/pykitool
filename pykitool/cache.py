import threading
from datetime import timedelta
from typing import Optional

import requests_cache
from hutool import LRUCache

# ================================ LRU 缓存 ================================

# LRU 缓存单例
_LRU_LOCK: threading.Lock = threading.Lock()
_LRU_INSTANCE: Optional[LRUCache] = None


# 获取 LRU 缓存单例
def get_lru_cache(max_size: int = 100) -> LRUCache:
    global _LRU_INSTANCE
    if _LRU_INSTANCE is None:
        with _LRU_LOCK:
            if _LRU_INSTANCE is None:
                _LRU_INSTANCE = LRUCache(capacity=max_size)
    return _LRU_INSTANCE


# ================================ 请求缓存 ================================

_REQUEST_LOCK: threading.Lock = threading.Lock()
_REQUEST_INSTANCE: Optional[requests_cache.CachedSession] = None


# 获取带缓存的请求会话
def get_request_session(cache_path: requests_cache.StrOrPath = "cache", timeout: int = 3600) -> requests_cache.CachedSession:
    global _REQUEST_INSTANCE
    if _REQUEST_INSTANCE is None:
        with _REQUEST_LOCK:
            if _REQUEST_INSTANCE is None:
                _REQUEST_INSTANCE = requests_cache.CachedSession(
                    cache_name=cache_path,
                    backend="filesystem",
                    expire_after=timedelta(seconds=timeout),
                    ignored_parameters=[
                        "Authorization",
                        "X-API-KEY",
                        "access_token",
                        "key",
                        "api_key",
                        "trustedclienttoken",
                        "Ocp-Apim-Subscription-Key",
                    ],
                )
    return _REQUEST_INSTANCE


# ================================ 调用示例 ================================


if __name__ == "__main__":

    # 获取 LRU 缓存实例
    cache = get_lru_cache(max_size=3)

    # 设置缓存
    cache.put("key1", {"data": "value1"})
    cache.put("key2", {"data": "value2"})
    cache.put("key3", {"data": "value3"})
    cache.put("key4", {"data": "value4"})

    # 获取缓存
    print(cache.get("key1"))  # 输出: None
    print(cache.get("key4"))  # 输出: {'data': 'value4'}

    # 删除缓存
    print(cache.get("key2"))  # 输出: {'data': 'value2'}
    cache.remove("key2")
    print(cache.get("key2"))  # 输出: {'data': 'value2'}

    # 清空所有缓存
    cache.clear()

    # ==================== 请求缓存会话示例 ====================

    # 获取带缓存的请求会话
    # session = get_request_session()

    # 发送请求（会自动缓存）
    # URL = "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list"
    # params = {"trustedclienttoken": "6A5AA1D4EAFF4E9FB37E23D68491D6F4"}
    # response = session.get(URL, params=params, timeout=30, verify=False)
    # print(response.text)
