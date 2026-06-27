import builtins
import inspect
import os
import sys
import warnings

import urllib3

# 忽略
warnings.filterwarnings("ignore")

# 禁用在使用不安全的 HTTPS 请求时产生的警告
urllib3.disable_warnings()

# 关闭
import logging
import threading
import time

from loguru import logger

# 格式化
format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:<5}</level> {thread:<5} <cyan>{file}:{line}</cyan> - {message}"
# format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:<7}</level> | <yellow>{thread}</yellow> | <cyan>{file}:{function}:{line}</cyan> - <level>{message}</level>"

# 白名单列表
WHITELIST = []

# ================================ 目录 ================================

# 可替换的日志目录获取函数（默认返回 logs，支持外部注入）
_log_dir_getter: callable = lambda: "logs"


# 默认目录
def get_log_dir() -> str:
    return _log_dir_getter()


# 供外部注入自定义日志目录获取函数
def set_log_dir_getter(fn: callable):
    """注入自定义日志目录获取函数，注入后调用 update_log_level() 立即生效。

    示例::

        # 从配置动态读取
        set_log_dir_getter(lambda: const.DIR_LOGS)
        update_log_level()

        # 直接指定固定目录
        set_log_dir_getter(lambda: "/var/log/myapp")
        update_log_level()
    """
    global _log_dir_getter
    _log_dir_getter = fn


# ================================ 级别 ================================

# 可替换的日志级别获取函数（默认返回 INFO，支持外部注入）
_log_level_getter: callable = lambda: "INFO"


# 默认级别
def get_log_level() -> str:
    return _log_level_getter()


# 供外部注入自定义日志级别获取函数
def set_log_level_getter(fn: callable):
    """注入自定义日志级别获取函数，注入后调用 update_log_level() 立即生效。

    示例::

        # 从配置动态读取
        set_log_level_getter(lambda: config.LOG_LEVEL)
        update_log_level()

        # 直接指定固定级别
        set_log_level_getter(lambda: "DEBUG")
        update_log_level()
    """
    global _log_level_getter
    _log_level_getter = fn


# 拦截器
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # 只处理属于白名单的模块
        if not any(record.name.startswith(whitelisted) for whitelisted in WHITELIST):
            if get_log_level() == "DEBUG":
                print(f"{record.name} -> {record.getMessage()}")
            return
        # 尝试获取 loguru 的级别名，失败则使用原始 levelno
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


# 启动器
class StartupTimer:
    def __init__(self):
        self.start_time = time.perf_counter()
        self.last_mark = self.start_time
        self.records = []
        self.lock = threading.Lock()

    def _get_caller_info(self):
        frame = inspect.currentframe().f_back.f_back
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        return f"{filename}:{lineno}"

    # 跟踪
    def track(self, tag=None, print: bool = True):
        with self.lock:
            now = time.perf_counter()
            delta = now - self.last_mark
            total = now - self.start_time

            if tag is None:
                tag = self._get_caller_info()

            self.records.append((tag, delta, total))

            self.last_mark = now
            if print:
                logger.info(f"[StartupTimer] {tag}: +{delta*1000:07.2f} ms (total {total*1000:07.2f} ms)")

    # 计算总时长
    def total_time(self):
        return time.perf_counter() - self.start_time

    # 摘要输出
    def dump(self):
        for tag, delta, total in self.records:
            print(f"{tag:12} | +{delta*1000:07.2f} ms | total {total*1000:07.2f} ms")


# 初始化
class LoguruLogger:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            # 单利模式
            cls._instance = super(LoguruLogger, cls).__new__(cls)
            cls._instance._configure_logger()
            # 清空默认自带的日志处理器
            loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
            for log in loggers:
                log.handlers = []
            # loguru 接管 logging
            logging.basicConfig(handlers=[InterceptHandler()], level=0)
            # loguru 接管 print()
            # builtins.print = logger.info
            # 设置 comtypes 包的日志级别为 WARNING，屏蔽其 INFO 级别的日志
        return cls._instance

    def _configure_logger(self):
        # 获取日志级别
        current_level = get_log_level()
        # 获取日志
        self.logger = logger
        # 移除默认日志输出
        self.logger.remove()
        # 配置控制台输出格式
        self.logger.add(sys.stdout, level=current_level, format=format, colorize=True)
        # 配置文件输出并启用轮转 - 按日期轮转（每天午夜）和文件大小轮转
        log_dir = get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        self.logger.add(log_dir + "/creator_{time:YYYY-MM-DD}.log", rotation="00:00", level=current_level, format=format, colorize=False)

    def update_log_level(self):
        # 更新日志级别配置
        self._configure_logger()


# 重试
def retry_print(retry_state):
    retry = retry_state.retry_object
    stop = retry.stop
    max_attempts = getattr(stop, "max_attempt_number", "?")
    logger.warning(f"Retrying {retry_state.attempt_number}/{max_attempts} time(s), {retry_state.fn.__name__} -> {retry_state.outcome.exception()}, waiting {retry_state.next_action.sleep} seconds before retrying.")


# 禁用
def disable_print():

    # 空方法，以便于禁止输出
    def no_print(*args, **kwargs):
        pass

    original_print = builtins.print
    builtins.print = no_print
    return original_print


# 恢复
def restore_print(original_print):
    if original_print:
        builtins.print = original_print


# 更新配置
def update_cfg():
    if LoguruLogger._instance:
        LoguruLogger._instance.update_log_level()


if not LoguruLogger._instance:
    LoguruLogger()


if __name__ == "__main__":
    print("message.{}", 11)
    logging.info("message %s", 22)
    # 通过日志输出一些消息
    logger.trace("message.{}", 0)
    logger.debug("message.{}", 1)
    logger.info("message.{}", 2)
    logger.success("message.{}", 3)
    logger.warning("message.{}", 4)
    logger.error("message.{}", 5)
    logger.critical("message.{}", 6)
    logger.exception("message.{}", 7)
