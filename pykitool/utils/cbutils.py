import os

from pykitool.base import const
from pykitool.utils import cbruntime


# 判断是否为调试模式
def is_debug() -> bool:
    # 优先环境变量env -> 其次参数arg
    return os.environ.get(const.ENV_IS_DUBUG, cbruntime.get_arg(["--reload", "--debug"], False))


# ================================ 调用示例 ================================

if __name__ == "__main__":

    # 判断是否为调试模式
    print(is_debug())
