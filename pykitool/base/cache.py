import os
import sys

sys.path.insert(0, os.getcwd())

import threading
import time
from collections import OrderedDict
from datetime import timedelta
from typing import Any, Dict, Optional

import requests_cache
from loguru import logger

# ================================ KV 键值存储 ================================


# 简单的线程安全键值存储类
class kv:

    _store: Dict[str, Any] = {}  # 共享的存储字典
    _lock: threading.Lock = threading.Lock()  # 线程锁

    # 获取键值
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        with cls._lock:
            return cls._store.get(key, default)

    # 设置键值
    @classmethod
    def set(cls, key: str, value: Any) -> None:
        with cls._lock:
            cls._store[key] = value

    # 删除键值
    @classmethod
    def delete(cls, key: str) -> bool:
        with cls._lock:
            if key in cls._store:
                del cls._store[key]
                return True
            return False

    # 清空所有键值
    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._store.clear()

    # 获取所有键值
    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        with cls._lock:
            return cls._store.copy()

    # 检查键是否存在
    @classmethod
    def exists(cls, key: str) -> bool:
        with cls._lock:
            return key in cls._store

    # 获取存储大小
    @classmethod
    def size(cls) -> int:
        with cls._lock:
            return len(cls._store)


# ================================ LRU 缓存 ================================


# LRU 缓存类，支持超时和使用频率统计
class LruCache:

    # 初始化 LRU 缓存
    def __init__(self, max_size: int = 5, timeout: int = 3600, cleanup_interval: int = 300) -> None:
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_size: int = max_size
        self.timeout: int = timeout
        self.lock: threading.RLock = threading.RLock()  # 使用可重入锁避免死锁
        self.cleanup_interval: int = cleanup_interval
        self._stop_event: threading.Event = threading.Event()
        self._wakeup_event: threading.Event = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._start_cleanup_thread()

    # 后台清理线程工作函数
    def _cleanup_thread_worker(self) -> None:
        while not self._stop_event.is_set():
            # 计算下一个到期时间（在锁内读取状态）
            with self.lock:
                now = time.time()
                expire_times = []
                for v in self.cache.values():
                    t = v.get("timeout", self.timeout)
                    expire_times.append(v["last_used"] + t)

                if expire_times:
                    next_expire = min(expire_times) - now
                    # 等待到下一个到期时间或 cleanup_interval（取较小者），至少等待 1 秒
                    wait_time = max(1, int(min(self.cleanup_interval, next_expire))) if next_expire > 0 else 0
                else:
                    wait_time = self.cleanup_interval

            # 如果已有到期项应立即清理（wait_time == 0），否则等待唤醒或超时
            if wait_time == 0:
                with self.lock:
                    removed = self._cleanup_expired()
                    if removed:
                        logger.debug(f"LRU cache periodic cleanup removed {removed} items")
                continue

            # 等待：被唤醒（如 set() 调用）或超时到达
            fired = self._wakeup_event.wait(timeout=wait_time)
            # 清除唤醒标志以便下次重新计算
            self._wakeup_event.clear()
            # 循环回到开头重新计算或检查停止条件

    # 启动后台清理线程
    def _start_cleanup_thread(self) -> None:
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._stop_event.clear()
            self._cleanup_thread = threading.Thread(target=self._cleanup_thread_worker, daemon=True)
            self._cleanup_thread.start()

    # 停止后台清理线程
    def _stop_cleanup_thread(self) -> None:
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_event.set()
            self._cleanup_thread.join(timeout=5)

    # 清理过期缓存
    def _cleanup_expired(self) -> int:
        now = time.time()
        keys_to_remove = [key for key, value in self.cache.items() if now - value["last_used"] > value.get("timeout", self.timeout)]
        for key in keys_to_remove:
            del self.cache[key]
        return len(keys_to_remove)

    # 清理超出大小
    def _cleanup_size(self) -> None:
        # 先清理过期项
        self._cleanup_expired()
        # 如果仍超出大小限制，删除使用次数最少的项
        while len(self.cache) > self.max_size:
            # 使用 min 的 key 参数找到使用次数最少的项
            least_used_key = min(self.cache.keys(), key=lambda k: (self.cache[k]["usage"], self.cache[k]["last_used"]))
            del self.cache[least_used_key]

    # 获取缓存项
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                now = time.time()
                if now - self.cache[key]["last_used"] > self.cache[key].get("timeout", self.timeout):
                    del self.cache[key]
                    return None
                self.cache[key]["last_used"] = now
                self.cache[key]["usage"] += 1
                return self.cache[key]["obj"]
            return None

    # 设置缓存项
    def set(self, key: str, obj: Any, timeout: Optional[int] = None) -> None:
        with self.lock:
            # 移动到末尾
            if key in self.cache:
                self.cache.move_to_end(key)
            # 设置缓存
            self.cache[key] = {
                "obj": obj,
                "last_used": time.time(),
                "usage": 1,
                "timeout": timeout or self.timeout,
            }
            # 超出大小限制时清理
            self._cleanup_size()

    # 获取缓存大小
    def size(self) -> int:
        with self.lock:
            return len(self.cache)

    # 获取缓存状态
    def status(self, print_log: bool = False) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            result = {
                key: {
                    "last_used": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value["last_used"])),
                    "usage": value["usage"],
                    "timeout": value.get("timeout", self.timeout),
                }
                for key, value in self.cache.items()
            }
        if print_log:
            logger.info(f"LRU Cache Status: {result}")
        return result

    # 检查缓存项是否存在
    def exists(self, key: str) -> bool:
        with self.lock:
            return key in self.cache

    # 删除指定
    def delete(self, key: str) -> bool:
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    # 清理过期和超出限制的缓存项
    def clear(self) -> int:
        with self.lock:
            return self._cleanup_expired()

    # 清空所有缓存
    def clear_all(self) -> None:
        with self.lock:
            self.cache.clear()

    # 析构函数，确保线程正确关闭
    def __del__(self) -> None:
        """析构时停止后台清理线程"""
        self._stop_cleanup_thread()


# LRU 缓存单例
_LRU_INSTANCE: Optional[LruCache] = None
_LRU_LOCK: threading.Lock = threading.Lock()


# 获取 LRU 缓存单例
def get_lru_cache(max_size: int = 100, timeout: int = 3600, clean_interval: int = 1800) -> LruCache:
    global _LRU_INSTANCE
    if _LRU_INSTANCE is None:
        with _LRU_LOCK:
            if _LRU_INSTANCE is None:
                try:
                    _LRU_INSTANCE = LruCache(max_size=max_size, timeout=timeout, cleanup_interval=clean_interval)
                except (AttributeError, TypeError) as e:
                    logger.warning(f"Failed to load cache config, using defaults: {e}")
                    _LRU_INSTANCE = LruCache()
    return _LRU_INSTANCE


# ================================ 请求缓存会话 ================================


_REQUEST_SESSION: Optional[requests_cache.CachedSession] = None
_REQUEST_LOCK: threading.Lock = threading.Lock()


# 获取带缓存的请求会话
def get_request_session(cache_name: requests_cache.StrOrPath = "cache", timeout: int = 3600) -> requests_cache.CachedSession:
    global _REQUEST_SESSION
    if _REQUEST_SESSION is None:
        with _REQUEST_LOCK:
            if _REQUEST_SESSION is None:
                try:
                    timeout = timeout
                except (AttributeError, TypeError) as e:
                    logger.warning(f"Failed to load cache config, using default timeout: {e}")
                    timeout = 3600
                _REQUEST_SESSION = requests_cache.CachedSession(
                    cache_name=cache_name,
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
    return _REQUEST_SESSION


# ================================ 调用示例 ================================


if __name__ == "__main__":

    # ==================== KV 键值存储示例 ====================

    # 设置键值
    # kv.set("username", "Alice")
    # print(kv.get("username"))  # 输出: Alice

    # 设置多个键值
    # kv.set("age", 25)
    # print(kv.get_all())  # 输出: {'username': 'Alice', 'age': 25}

    # 检查键是否存在
    # print(kv.exists("username"))  # 输出: True

    # 获取存储大小
    # print(kv.size())  # 输出: 2

    # 删除键值
    # kv.delete("username")
    # print(kv.get("username"))  # 输出: None

    # 清空所有键值
    # kv.clear()
    # print(kv.get_all())  # 输出: {}

    # ==================== LRU 缓存示例 ====================

    # 获取 LRU 缓存实例
    # cache = get_lru_cache()

    # 设置缓存
    # cache.set("key1", {"data": "value1"})
    # cache.set("key2", {"data": "value2"}, timeout=60)  # 自定义超时时间

    # 获取缓存
    # result = cache.get("key1")
    # print(result)  # 输出: {'data': 'value1'}

    # 检查缓存是否存在
    # print(cache.exists("key1"))  # 输出: True

    # 获取缓存状态
    # cache.status(print_log=True)

    # 删除缓存
    # cache.delete("key1")

    # 清理过期缓存
    # removed_count = cache.clear()
    # print(f"Removed {removed_count} expired items")

    # 清空所有缓存
    # cache.clear_all()

    # ==================== 请求缓存会话示例 ====================

    # 获取带缓存的请求会话
    # session = get_request_session()

    # 发送请求（会自动缓存）
    # URL = "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list"
    # params = {"trustedclienttoken": "6A5AA1D4EAFF4E9FB37E23D68491D6F4"}
    # response = session.get(URL, params=params, timeout=30, verify=False)
    # print(response.text)

    pass
