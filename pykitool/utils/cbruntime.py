import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from tqdm import tqdm

from pykitool.utils import cbstr

# 延迟初始化标志，避免模块导入时执行 subprocess
_ensurepip_initialized = False

# ====================================================== package ======================================================


# 读取包名称（去除版本号）
def read_requirements_names(file_path: str) -> List[str]:
    package_names = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):  # 跳过空行和注释
                name = line.split("==")[0]
                name = name.split("[", 1)[0].strip()
                package_names.append(name)
    return package_names


# 打印并返回平台、Python 版本和 requirements 中包的实际安装版本
def get_environment_package(requirements_path: str = "requirements.txt") -> Dict[str, Any]:
    _package_versions = {}

    # 系统通用信息
    info: Dict[str, Any] = {
        "Platform": platform.system(),
        "Python version": platform.python_version(),
        "==============": "",
    }

    # 获取每个包的安装版本
    for name in read_requirements_names(requirements_path):
        try:
            _package_versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            _package_versions[name] = "N/A"

    # 合并信息
    info.update(_package_versions)
    return info


# 检查指定的所有包是否都已安装
def is_installed(packages: List[str]) -> bool:
    for package_name in packages:
        try:
            metadata.version(package_name)
        except metadata.PackageNotFoundError:
            return False
    return True


# 包管理（安装或卸载）
def package_manage(packages: List[str], uninstall: bool = False, default_index: str = "https://pypi.org/simple") -> None:
    # 解析
    def is_installed_with_version(package_spec: str) -> bool:
        if "==" in package_spec:
            pkg_name, expected_ver = package_spec.split("==")
        else:
            pkg_name, expected_ver = package_spec, None
        try:
            installed_ver = metadata.version(pkg_name)
            return installed_ver == expected_ver if expected_ver else True
        except metadata.PackageNotFoundError:
            return False

    # 卸载
    if uninstall:
        installed = [pkg for pkg in packages if is_installed_with_version(pkg)]
        if not installed:
            print("ℹ️ None of the specified packages are installed.")
            return
        print(f"🗑️ Uninstalling packages: {installed}")
        cmd = ["uv", "pip", "uninstall", "-y", *installed]
        subprocess.check_call(cmd)

    # 安装
    else:
        missing = [pkg for pkg in packages if not is_installed_with_version(pkg)]
        if not missing:
            print("✅ All packages are already installed.")
            return
        print(f"📦 Installing missing packages: {missing}")
        cmd = ["uv", "pip", "install", *missing, f"--default-index={default_index}"]
        subprocess.check_call(cmd)


# 初始化 ensurepip
def get_ensurepip():
    global _ensurepip_initialized
    if not _ensurepip_initialized:
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _ensurepip_initialized = True


# ====================================================== environment ======================================================


# 获取环境变量
def get_env(key: str, val: Any = None, print: bool = False) -> Any:
    val = os.getenv(key, val)
    if val == None and print:
        logger.warning("environment variable not found '{}'", key)
    return val


# 获取命令行参数
def get_arg(keys: List[str], default: Any = None) -> Any:
    # 根据default推断转换函数
    cast_func = None
    if default is not None:
        if isinstance(default, bool):
            return any(arg in sys.argv for arg in keys)
        if isinstance(default, int):
            cast_func = int
        elif isinstance(default, float):
            cast_func = float
        elif isinstance(default, str):
            cast_func = str
        else:
            cast_func = lambda x: x
    else:
        # default是None，返回字符串
        cast_func = lambda x: x

    for i, arg in enumerate(sys.argv):
        if arg in keys:
            try:
                value = cast_func(sys.argv[i + 1])
                return value
            except (IndexError, ValueError):
                logger.error(f"Invalid value for {arg}, using default: {default}")
                return default
    return default


# ====================================================== subprocess ======================================================


# 拆分命令列表
def split_cmd(cmd_list: List[str]) -> List[str]:
    """
    把 cmd 列表里的每个元素拆分空格，但只拆第一个空格，将参数和值分开。例如 "--host 0.0.0.0" -> ["--host", "0.0.0.0"]
    路径或其他包含空格的值保持完整。
    保留单独的选项（没有空格）不变
    """
    result = []
    for item in cmd_list:
        if " " in item:
            key, value = item.split(" ", 1)  # 只拆第一个空格
            result.append(key)
            result.append(value)
        else:
            result.append(item)

    print(" ".join(f'"{c}"' if " " in c else c for c in result))
    return result


# 执行子进程并等待完成
def subprocess_run(cmd, cwd: str = None, isclean: bool = False, check: bool = True) -> str:
    # 复制环境
    env = os.environ.copy()
    # 是否清除
    if isclean:
        # 关键：清除当前虚拟环境信息，让 uv 自己判断目标项目环境
        env.pop("VIRTUAL_ENV", None)
        env.pop("PYTHONPATH", None)

    # 执行命令
    if check:
        result = subprocess.run(
            args=cmd,
            cwd=cwd,
            capture_output=True,  # 捕获输出
            text=True,  # 自动解码输出为 str
            encoding="utf-8",  # 编码
            env=env,  # 环境
            check=check,  # 出错时抛出异常
        )
        return result.stdout.strip() + "\n" + result.stderr.strip()
    else:
        subprocess.run(
            args=cmd,
            cwd=cwd,
            stdout=None,
            stderr=None,
            env=env,  # 环境
        )


# 启动独立子进程
def subprocess_popen(cmd, cwd: str = None, log: str = None, isclean: bool = False) -> subprocess.Popen:
    # 复制环境
    env = os.environ.copy()
    # 是否清除
    if isclean:
        # 关键：清除当前虚拟环境信息，让 uv 自己判断目标项目环境
        env.pop("VIRTUAL_ENV", None)
        env.pop("PYTHONPATH", None)

    # 输出重定向（写入文件、输出控制台）
    if log:
        # 打开日志文件
        f = open(log, "a", encoding="utf-8")
        stdout = f
        stderr = subprocess.STDOUT
        if os.name == "nt":
            # Console 打印
            stdout = None
            stderr = None

        # 执行命令
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
            text=True,  # 自动解码输出为 str
            encoding="utf-8",  # 编码
            close_fds=True,  # 关闭不必要的文件描述符
            env=env,  # 环境
            bufsize=1,  # 行缓冲
        )
        # Colab 实时打印
        if not log and os.name != "nt":
            for line in proc.stdout:
                print(line, end="")

        return proc
    else:
        # 直接继承控制台
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=None,
            stderr=None,
            env=env,  # 环境
        )


# 消费子进程输出，防止管道堵塞
def consume_proc_output(prefix: str, proc: subprocess.Popen) -> None:
    try:
        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                if line:
                    logger.info("[{}] {}", prefix, line.rstrip())
    except Exception as e:
        logger.warning("Error consuming process output: {}", e)


# 重启
def reboot(py_path: str = sys.executable, delay: int = 3) -> None:
    try:
        from pyngrok import ngrok

        ngrok_available = True
    except ImportError:
        ngrok_available = False

    # 延迟重启函数
    def delayed_restart():

        # 停止代理
        is_ngrok = get_arg(["--ngrok"], False)
        if ngrok_available and is_ngrok:
            try:
                ngrok.kill()
            except Exception as e:
                logger.warning(f"ngrok disconnect failed: {str(e)}")

        # 倒计时
        for i in range(delay, 0, -1):
            logger.info(f"{i}s")
            time.sleep(1)
        logger.info("reboot...")

        # 从环境变量中获取启动参数
        try:
            argv = json.loads(os.environ["REBOOT_ARGS"])
        except Exception as e:
            logger.error("Failed to load REBOOT_ARGS:", str(e))
            argv = sys.argv

        # 重新启动
        py_path_abs = os.path.abspath(py_path)
        # 打印调试命令
        logger.info(" ".join(f'"{a}"' if " " in a else a for a in [py_path_abs, *argv]))
        # os.execl(py_path_abs, py_path_abs, *argv)
        subprocess.run([py_path_abs, *argv])

    # 启动线程来延迟重启
    threading.Thread(target=delayed_restart).start()


# 打开浏览器
def open_browser(uri: str) -> None:
    import webbrowser

    try:
        if uri.startswith("http://") or uri.startswith("https://"):
            webbrowser.open(uri)
        else:
            webbrowser.open(Path(uri).as_uri())
    except Exception as e:
        logger.error(f"{uri} -> open error: {str(e)}")


# ====================================================== process ======================================================


# 等待端口可访问
def wait_port(host: str, port: int, timeout: int = 5) -> bool:
    host = "127.0.0.1" if host == "0.0.0.0" else host
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            time.sleep(0.1)
    return False


# 删除指定端口进程
def kill_process(pid: int = None, port: int = None, force: bool = True) -> bool:
    """
    Kill a process by PID or by port (cross-platform).

    Args:
        pid (int, optional): Process ID to kill.
        port (int, optional): Port number to kill processes using it.
        force (bool): Force kill (Windows: /F, Unix: SIGKILL). Default True.
    """
    system = platform.system()

    if pid is None and port is None:
        raise ValueError("Either pid or port must be provided.")

    # --- Case 1: Kill by PID ---
    if pid is not None:
        try:
            if system == "Windows":
                cmd = ["taskkill", "/PID", str(pid)]
                if force:
                    cmd.append("/F")
                subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
            logger.info(f"Process {pid} terminated successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to terminate process {pid}: {str(e)}")
            return False

    # --- Case 2: Kill by port ---
    pids = []
    try:
        if system == "Windows":
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    pids.append(pid)
        else:
            result = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True)
            pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except Exception as e:
        logger.error(f"Failed to find processes on port {port}: {str(e)}")
        return False

    if not pids:
        logger.debug(f"No process found listening on port {port}.")
        return False

    success = False
    for pid in pids:
        logger.info(f"Killing process {pid} listening on port {port}...")
        success = kill_process(pid=int(pid), force=force) or success

    return success


# 杀掉残余的 localtunnel 进程，防止 subdomain 被占用导致名称随机
def kill_processes_tunnel(port: int) -> None:
    import psutil

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if ("localtunnel" in cmdline or " lt " in cmdline or cmdline.endswith(" lt")) and str(port) in cmdline:
                proc.terminate()
                logger.info(f"Killed localtunnel process pid={proc.pid} cmdline={cmdline!r}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


# ====================================================== checker ======================================================

# 工具配置字典
TOOL_CONFIG = {
    "uv": {"display_name": "uv", "version_pattern": r"uv\s+([\d.]+\d)"},
    "python": {"display_name": "Python", "version_pattern": r"Python\s+([\d.]+\d)"},
    "pip": {"display_name": "pip", "version_pattern": r"pip\s+([\d.]+\d)"},
    "ffmpeg": {"display_name": "ffmpeg", "version_pattern": r"ffmpeg\s+version\s+([\d.]+\d)"},
    "ffprobe": {"display_name": "ffprobe", "version_pattern": r"ffprobe\s+version\s+([\d.]+\d)"},
    "git": {"display_name": "git", "version_pattern": r"git\s+version\s+([\d.]+\d)"},
    "aria2c": {"display_name": "aria2", "version_pattern": r"aria2\s+version\s+([\d.]+\d)"},
}


# 检查指定的软件是否已安装
class ToolEnvChecker:

    def __init__(self, name: str, fallback_dirs: Union[str, List[str]] = None):
        self.name = name.lower()
        if isinstance(fallback_dirs, str):
            self.fallback_dirs = [os.path.abspath(fallback_dirs)]
        elif isinstance(fallback_dirs, list):
            self.fallback_dirs = [os.path.abspath(d) for d in fallback_dirs]
        else:
            self.fallback_dirs = []
        self.order = []
        self._tool_path_cache: Optional[str] = None
        self._version_cache: Optional[str] = None

    # 查找工具路径
    def find_tool(self, auto_add_to_path: bool = True) -> Optional[str]:
        if self._tool_path_cache:
            return self._tool_path_cache

        # 1. 优先系统 PATH
        tool_path = shutil.which(self.name)
        if tool_path:
            self._tool_path_cache = Path(tool_path).as_posix()
            return self._tool_path_cache

        # 2. 再查备用目录
        for directory in self.fallback_dirs:
            if os.path.isdir(directory):
                for fname in os.listdir(directory):
                    fpath = os.path.join(directory, fname)
                    if fname.lower().startswith(self.name) and os.access(fpath, os.X_OK):
                        if auto_add_to_path:
                            self._add_to_path(directory)
                        self._tool_path_cache = Path(fpath).as_posix()
                        return self._tool_path_cache
        return None

    # 添加环境变量
    def _add_to_path(self, directory: str) -> None:
        directory = os.path.abspath(directory)
        if directory not in self.order:
            self.order.append(directory)
        current_path = os.environ.get("PATH", "")
        paths = current_path.split(os.pathsep)
        paths = [p for p in paths if p not in self.order]
        new_path = os.pathsep.join(self.order + paths)
        os.environ["PATH"] = new_path
        logger.info(f"Added {directory} to PATH")

    # 获取工具版本
    def get_version(self, tool_path: Optional[str] = None, version_arg: str = "--version") -> Optional[str]:
        if self._version_cache:
            return self._version_cache

        try:
            if tool_path is None:
                tool_path = self.find_tool()
            if tool_path is None:
                return None

            result = subprocess.run([tool_path, version_arg], capture_output=True, text=True, timeout=5)
            version = result.stdout.strip() or result.stderr.strip()
            self._version_cache = version if version else None
            return self._version_cache
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.debug(f"Failed to get version for {self.name}: {str(e)}")
            return None

    # 检查工具是否可用
    def is_available(self) -> bool:
        return self.find_tool() is not None


# 统一的工具检查函数
def check_tool(tool_name: str, show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    checker = ToolEnvChecker(tool_name)
    tool_path = checker.find_tool()
    config = TOOL_CONFIG.get(tool_name, {})
    display_name = config.get("display_name", tool_name)

    if not tool_path:
        logger.warning(f"{tool_name} is not available")
        if show_print:
            print(f"{cbstr.pad_string(display_name + ' Not Found', align='left', length=length)} not available")
        else:
            print(f"{display_name} Not Found")
        return checker

    raw_version = checker.get_version()
    version = "Unknown"
    if raw_version:
        pattern = config.get("version_pattern")
        if pattern:
            match = re.search(pattern, raw_version, re.IGNORECASE)
            if match:
                version = match.group(1)
        else:
            version = raw_version.split()[0] if raw_version else "Unknown"

    if show_print:
        label = f"{display_name} {version}"
        print(f"{cbstr.pad_string(label, align='left', length=length)} Using {tool_path}")
    else:
        print(f"{display_name} {version}")
        print(f"Using {tool_path}")

    return checker


# ====================================================== uv ======================================================


# 检查 uv
def check_uv(show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    return check_tool(tool_name="uv", show_print=show_print, length=length)


# ====================================================== py ======================================================


# 检查 py
def check_python(show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    return check_tool(tool_name="python", show_print=show_print, length=length)


# ====================================================== ffmpeg ======================================================


# 是否是指定类型
def is_codec_type(path: str) -> str:
    try:
        streams = process_metadata(path, "streams", [])
        has_video = any(s["codec_type"] == "video" for s in streams)
        has_audio = any(s["codec_type"] == "audio" for s in streams)
        if has_video and not has_audio:
            return "video"  # 纯视频（无音轨）
        elif has_audio and not has_video:
            return "audio"  # 纯音频
        elif has_audio and has_video:
            return "video+audio"  # 常见的带声音的视频文件
        else:
            return "unknown"  # 没有检测到音频/视频流
    except Exception as e:
        return "unknown"


# 检查 ffplay
def check_ffplay(show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    return check_tool(tool_name="ffplay", show_print=show_print, length=length)


# 检查 ffmpeg
def check_ffmpeg(show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    return check_tool(tool_name="ffmpeg", show_print=show_print, length=length)


# 检查 ffprobe
def check_ffprobe(show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    return check_tool(tool_name="ffprobe", show_print=show_print, length=length)


# 获取元数据
def process_metadata(path: str, metadata: str = "format", default: Union[Dict, List] = None) -> Union[Dict, List[Dict]]:
    try:
        import ffmpeg

        ffmpeg_available = True
    except ImportError:
        ffmpeg_available = False

    if default is None:
        default = {}
    if not ffmpeg_available:
        return default
    try:
        probe = ffmpeg.probe(path)
        return probe.get(metadata, default)
    except Exception as e:
        logger.error(f"Error: {path} {str(e)}")
        return default


# 运行 ffmpeg 命令并显示进度
def process_ffmpeg(duration: float, cmd: List[str], debug: bool = False) -> None:
    logger.debug("command: {}", " ".join(cmd))
    checker = check_ffmpeg()
    if not checker.is_available():
        logger.error("Ffmpeg is not available, please install ffmpeg first")
        return
    # debug 模式：捕获所有输出，便于调试
    if debug:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg failed (debug mode). returncode={res.returncode}\n\nSTDERR:\n{res.stderr}")
        return
    # 启动子进程
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, bufsize=1, encoding="utf-8")  # drop stdout to avoid filling buffer
    # 进度条
    pbar = tqdm(total=round(duration, 2), unit="s", ncols=100, desc="Processing", dynamic_ncols=True)
    # 解析 stderr 中的 time=HH:MM:SS.xx
    time_pattern = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
    # 保留stderr的尾部用于调试
    last_lines = deque(maxlen=500)
    prev_sec = 0.0
    # 实时读取 stderr
    try:
        for line in iter(proc.stderr.readline, ""):
            if not line:
                break
            last_lines.append(line)
            line = line.strip()
            m = time_pattern.search(line)
            if m:
                h, mm, ss = m.groups()
                sec = int(h) * 3600 + int(mm) * 60 + float(ss)
                delta = max(0.0, sec - prev_sec)
                if delta > 0:
                    pbar.update(delta)
                    prev_sec = sec
    finally:
        try:
            remaining = proc.stderr.read()
            if remaining:
                last_lines.append(remaining)
        except Exception:
            pass
        pbar.close()
        proc.wait()
    # 检查返回码
    if proc.returncode != 0:
        tail = "".join(last_lines)
        raise RuntimeError(f"FFmpeg process failed (returncode={proc.returncode}). Last stderr lines:\n{tail}")


# 删除 ffmpeg 进程
def terminate_ffmpeg():
    import psutil

    # current_user = getpass.getuser()
    for proc in psutil.process_iter(attrs=["pid", "name", "username"]):
        # if proc.info["username"] != current_user:
        #     continue
        name = proc.info.get("name", "")
        if name and "ffmpeg" in name.lower():
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception as e:
                    print(f"Failed to terminate ffmpeg process {proc.pid}: {str(e)}")


# ====================================================== git ======================================================


# 检查 git
def check_git(show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    return check_tool(tool_name="git", show_print=show_print, length=length)


# 获取版本信息
def process_git_info():

    process_git_info = {"branch": "unknown", "date": "unknown", "hash": "unknown"}

    try:
        repo_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        # 获取分支名
        result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            process_git_info["branch"] = result.stdout.strip()

        # 获取最后提交时间
        result = subprocess.run(["git", "log", "-1", "--format=%ci"], cwd=repo_path, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            process_git_info["date"] = result.stdout.strip()

        # 获取短 commit hash
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_path, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            process_git_info["hash"] = result.stdout.strip()
    except Exception as e:
        print(f"Warning: Failed to get git info - {e}")

    return process_git_info


# ====================================================== aria2 ======================================================


# 检查 aria2c
def check_aria2c(show_print: bool = False, length: int = 15) -> ToolEnvChecker:
    return check_tool(tool_name="aria2c", show_print=show_print, length=length)


# 多线程下载
def process_aria2(url: str, save_folder: str = None, filename: str = None) -> str:
    # 默认下载地址
    if not save_folder:
        save_folder = tempfile.gettempdir()

    # 默认文件名
    if not filename:
        filename = url.split("/")[-1]

    # 创建文件夹（如果文件夹不存在）
    Path(save_folder).mkdir(parents=True, exist_ok=True)

    # 拼接完整的文件路径
    file_path = Path(os.path.join(save_folder, filename)).as_posix()

    # 文件是否存在
    if os.path.exists(file_path):
        return file_path

    # 检查工具
    checker = check_aria2c()
    if not checker.is_available():
        logger.error("Aria2c is not available, please install aria2c first")
        return None

    # 默认连接数
    connections = 16

    # 构建命令
    cmd = [
        "aria2c",
        url,
        f"--dir {save_folder}",
        "--continue=true",  # 断点续传
        f"--max-connection-per-server {str(connections)}",  # 每服务器连接数
        f"--split {str(connections)}",  # 下载分片数量
        "--min-split-size=1M",  # 每个分片最小1MB
        "--auto-file-renaming=false",  # 禁止重复重命名
        "--retry-wait=3",  # 失败重试等待时间
        "--max-tries=0",  # 无限重试
        "--console-log-level=warn",  # 控制台日志级别（warn以上）
    ]

    # 执行命令
    proc = subprocess.Popen(
        split_cmd(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # 进度条 (匹配类似 “[#1 12.3MiB/3.6GiB(0%) CN:16 DL:1.2MiB]” 的行)
    pattern = re.compile(r"\((\d+)%\)")
    pbar = tqdm(total=100, unit="%", desc=filename, dynamic_ncols=True)
    last_percent = 0
    for line in proc.stdout:
        line = line.strip()
        match = pattern.search(line)
        if match:
            percent = int(match.group(1))
            delta = percent - last_percent
            if delta > 0:
                pbar.update(delta)
                last_percent = percent
    proc.wait()
    pbar.close()
    # 判断
    if proc.returncode == 0:
        logger.debug(f"File has been saved to: {file_path}")
    else:
        logger.error("Failed to download error_code: {}", proc.returncode)
    return file_path


# ================================ 调用示例 ================================


if __name__ == "__main__":

    # 获取环境变量
    print(get_env("PATH"))

    # 获取命令行参数
    print(get_arg(["--debug"], False))

    # 检查 Python
    check_python()

    # 检查 ffmpeg
    check_ffmpeg()

    # 检查包安装
    print(is_installed(["requests"]))

    # 获取环境包信息
    print(get_environment_package(r"D:\Projects\creator\creator-box\requirements.txt"))
