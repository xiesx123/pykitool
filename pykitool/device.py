import multiprocessing
import os
import platform
import random
import subprocess
from typing import List, Optional, Union

import torch
from hutool import RandomUtil
from loguru import logger

from pykitool.base.enums import Platform

# ================================ os ================================


# 判断是否为 Windows 系统
def is_windows() -> bool:
    return platform.system().lower() == Platform.Window.value


# 判断是否为 Linux 系统
def is_linux() -> bool:
    return platform.system().lower() == Platform.Linux.value


# 判断是否为 Mac 系统
def is_mac() -> bool:
    return platform.system().lower() == Platform.Mac.value


# ================================ cpu ================================


# 获取可用的 CPU 核心数
def cpu_available_count() -> int:
    try:
        # 获取所有核心
        all_cpu_count = multiprocessing.cpu_count()
        # 根据系统 CPU 核心数，智能分配一个合理的并发线程数 cpu_count
        cpu_count = max(int(all_cpu_count * 2 / 3), 1)
        # 如果小于4
        if cpu_count < 4:
            # 用总核心数 - 1，仍然保留 1 个核心不占用，防止系统卡死
            cpu_count = max(all_cpu_count - 1, 1)
        return cpu_count
    except (OSError, NotImplementedError) as e:
        logger.warning(f"Failed to get CPU count: {e}, using default value 1")
        return 1


# ================================ gpu ================================


# 判断 NVIDIA 是否可用
def is_nvidia_available() -> bool:
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


# 判断 CUDA 是否可用
def is_cuda_available() -> bool:
    import torch

    return torch.cuda.is_available()


# 获取显卡标识（CPU 或 GPU）
def identifier(multiple: bool = False) -> Union[str, List[torch.device]]:
    # 检查是否有可用的 CUDA 设备
    cuda_available = torch.cuda.is_available()
    device_str = "cuda" if cuda_available else "cpu"
    # 多设备支持
    if not multiple:
        return device_str
    else:
        if cuda_available:
            device_count = torch.cuda.device_count()
            return [torch.device(f"cuda:{i}") for i in range(device_count)]
        return [device_str]


# 清空 CUDA 显存缓存
@torch.no_grad()
def cuda_memory_clear() -> None:
    import torch

    # 清空 GPU 缓存
    torch.cuda.empty_cache()
    # 清空 CUDA 内存
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.ipc_collect()


# ================================ runtime ================================


# 获取 onnxruntime 版本
def onnxruntime_version():
    import onnxruntime as ort

    try:
        return f"{ort.__version__}+{ort.get_device().lower()}"
    except Exception as e:
        return "unknown"


# 设置随机种子，确保结果可复现
def set_seed(seed: Optional[int] = None, start: int = 10000000, end: int = 99999999) -> int:
    import numpy

    # 随机种子
    if seed is None:
        seed = RandomUtil.random_int(min_include=start, max_exclude=end)
    # 设置种子
    random.seed(seed)  # Python 内置随机模块
    os.environ["PYTHONHASHSEED"] = str(seed)  # Python 哈希种子（影响字典和集合的哈希值）
    numpy.random.seed(seed)  # NumPy 随机模块
    torch.manual_seed(seed)  # PyTorch CPU
    torch.cuda.manual_seed(seed)  # PyTorch GPU（单卡）
    torch.cuda.manual_seed_all(seed)  # 多GPU
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    logger.debug(f"Seed has been set to {seed}")
    return seed


# ================================ 调用示例 ================================


if __name__ == "__main__":

    # 判断系统类型
    print(f"Is Windows: {is_windows()}")
    print(f"Is Linux: {is_linux()}")
    print(f"Is Mac: {is_mac()}")

    # 获取 CPU 核心数
    print(f"Available CPU count: {cpu_available_count()}")

    # 判断 NVIDIA 是否可用
    print(f"Nvidia available: {is_nvidia_available()}")

    # 判断 CUDA 是否可用
    print(f"CUDA available: {is_cuda_available()}")

    # 获取多设备标识
    print(f"Device: {identifier(multiple=False)}")

    print(f"Devices: {identifier(multiple=True)}")

    # 清空 CUDA 显存缓存
    if is_cuda_available:
        cuda_memory_clear()
        print("CUDA memory cleared")

    # 设置随机种子
    print(f"Random seed: {set_seed()}")
