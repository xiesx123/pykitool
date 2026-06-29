import threading
import time
from typing import Any, Callable, TypeVar

from loguru import logger

# 泛型类型变量
T = TypeVar("T")

# ================================ 线程 ================================


def submit(func: Callable[..., Any], *args, **kwargs) -> None:
    """
    在后台守护线程中执行同步函数，fire-and-forget，不阻塞主线程，异常会被捕获并记录日志。

    适用场景：发日志、发通知、缓存清理等无需等待返回值的副作用操作。
    """

    def _safe() -> None:
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Background task error: {str(e)}")

    threading.Thread(target=_safe, daemon=True).start()


# ================================ 协程 ================================


# ================================ 调用示例 ================================


if __name__ == "__main__":

    # ---- 1. run_background：在后台线程中执行同步函数 ----
    def _sync_work(msg: str) -> None:
        time.sleep(3)
        print(f"[run_background] {msg}")

    submit(_sync_work, "running in background thread")
    print("start")
    time.sleep(5)
