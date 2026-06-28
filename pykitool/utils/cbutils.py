from pykitool.utils import cbruntime


# 判断是否为调试模式
def is_debug() -> bool:
    return cbruntime.get_arg(["--reload", "--debug"], False)


# ================================ 调用示例 ================================

if __name__ == "__main__":

    # 判断是否为调试模式
    print(is_debug())
