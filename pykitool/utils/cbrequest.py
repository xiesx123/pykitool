import os
import subprocess
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from hutool import NetUtil
from loguru import logger
from tqdm import tqdm

from pykitool.base.enums import BaseAbstractEnum, Platform
from pykitool.utils import cbfile, cbruntime

# ================================ 网络地址 ================================


# 获取本地服务地址
def get_localhost(is_https: bool = False, host: str = "127.0.0.1", port: int = 8000) -> str:
    scheme = "https" if is_https else "http"
    host = host or NetUtil.get_local_ip()
    port = cbruntime.get_arg(["-p", "--port"], port)
    return f"{scheme}://{host}:{port}"


# 批量获取归属地信息(ipapi)
def get_ipapi_locations_batch(ips: List[str]) -> Dict[str, Dict]:
    import random
    import time

    from pykitool.cache import get_lru_cache

    if not ips:
        return {}

    cache = get_lru_cache()
    results = {}
    ips_to_query = []

    # 1. 过滤本地 IP 并尝试从缓存获取
    for ip in ips:
        if not ip:
            continue

        if ip.startswith(("127.", "192.168.", "10.")):
            results[ip] = {"status": "success", "country": "Local", "regionName": "", "city": ""}
            continue

        cache_key = f"ip_loc_raw_{ip}"
        cached_loc = cache.get(cache_key)
        if cached_loc is not None:
            results[ip] = cached_loc
        else:
            ips_to_query.append(ip)

    # 去重
    ips_to_query = list(set(ips_to_query))

    # 2. 批量请求（最多重试 3 次）
    max_retries = 3
    for attempt in range(max_retries):
        if not ips_to_query:
            break

        logger.debug(f"Batch IP location query attempt {attempt + 1}/{max_retries}, querying {len(ips_to_query)} IPs")
        failed_ips = []

        # 按 100 个一批切分
        batch_size = 100
        for i in range(0, len(ips_to_query), batch_size):
            batch = ips_to_query[i : i + batch_size]
            url = "http://ip-api.com/batch?lang=zh-CN"
            try:
                resp = requests.post(url, json=batch, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data:
                        ip = item.get("query")
                        if not ip:
                            continue

                        if item.get("status") == "success":
                            results[ip] = item
                            # 写入缓存
                            cache.set(f"ip_loc_raw_{ip}", item, timeout=86400)
                        else:
                            failed_ips.append(ip)
                else:
                    logger.warning(f"Batch API returned status code: {resp.status_code}")
                    failed_ips.extend(batch)
            except Exception as e:
                logger.error(f"Batch IP location query failed: {e}")
                failed_ips.extend(batch)

            # 每批之间随机休眠 5-10 秒防屏蔽（如果是最后一部且没有失败的，可不休眠）
            if attempt < max_retries - 1 or len(ips_to_query) > batch_size:
                sleep_time = random.uniform(5, 10)
                logger.debug(f"Sleeping for {sleep_time:.2f} seconds before next batch/attempt")
                time.sleep(sleep_time)

        # 更新下次重试需要查询的 IP
        ips_to_query = failed_ips

    return results


# 获取归属地信息(ipapi)
def get_ipapi_location(ip: str) -> Dict[str, str]:
    from pykitool.cache import get_lru_cache

    if not ip:
        return {}

    cache = get_lru_cache()
    # 尝试从缓存中获取
    cache_key = f"ip_loc_raw_{ip}"
    cached_loc = cache.get(cache_key)
    if cached_loc is not None:
        return cached_loc

    # 忽略局域网/保留 IP
    if ip.startswith(("127.", "192.168.", "10.")):
        return {"status": "success", "country": "Local", "regionName": "", "city": ""}

    try:
        url = f"http://ip-api.com/json/{ip}?lang=zh-CN"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                # 写入缓存，1 天过期，避免频繁请求
                cache.set(cache_key, data, timeout=86400)
                return data
    except Exception as e:
        logger.error(f"Get IP location failed for {ip}: {e}")

    return {}


# 获取归属地信息(ip9 备用接口)
def get_ip9_location(ip: str) -> Dict[str, str]:
    from pykitool.cache import get_lru_cache

    if not ip:
        return {}

    cache = get_lru_cache()
    # 尝试从缓存中获取
    cache_key = f"ip_loc_ip9_{ip}"
    cached_loc = cache.get(cache_key)
    if cached_loc is not None:
        return cached_loc

    # 忽略局域网/保留 IP
    if ip.startswith(("127.", "192.168.", "10.")):
        return {"status": "success", "country": "Local", "regionName": "", "city": ""}

    try:
        url = f"https://ip9.com.cn/get?ip={ip}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ret") == 200:
                result_data = data.get("data", {})
                # 统一格式化为 ip-api 相同的结构
                formatted_data = {"status": "success", "country": result_data.get("country", ""), "regionName": result_data.get("prov", ""), "city": result_data.get("city", "")}
                # 写入缓存，1 天过期
                cache.set(cache_key, formatted_data, timeout=86400)
                return formatted_data
    except Exception as e:
        logger.error(f"Get IP location (ip9) failed for {ip}: {e}")

    return {}


# ================================ 连接验证 ================================


# 验证 HTTP 连接
def verify_connection(url: str = "https://www.google.com", proxy: Optional[Dict[str, str]] = None, timeout: float = 1.0, show_print: bool = False) -> bool:
    try:
        resp = requests.get(url, proxies=proxy, timeout=timeout)
        return resp.ok
    except requests.exceptions.Timeout:
        if show_print:
            logger.warning(f"Check {url} connection time out")
        return False
    except requests.exceptions.ConnectionError:
        if show_print:
            logger.warning(f"Check {url} connection error")
        return False
    except requests.exceptions.RequestException as e:
        if show_print:
            logger.warning(f"Check {url} connection exception: {str(e)}")
        return False


# ================================ 文件下载 ================================


# 通过 HTTP 下载文件
def http_download(url: str, save_folder: str = cbfile.tempdir(), filename: Optional[str] = None) -> str:
    import requests

    if not filename:
        filename = url.split("/")[-1]

    cbfile.mk(save_folder)
    file_path = cbfile.ap(os.path.join(save_folder, filename))

    if os.path.exists(file_path):
        logger.debug(f"File already exists: {file_path}")
        return file_path

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))

        with open(file_path, "wb") as file:
            for chunk in tqdm(
                response.iter_content(1024),
                total=total_size // 1024,
                unit="KB",
                desc=filename,
                dynamic_ncols=True,
            ):
                file.write(chunk)
        logger.debug(f"File saved to: {file_path}")
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed: {str(e)}")
        raise RuntimeError(f"Download failed: {str(e)}") from e
    except IOError as e:
        logger.error(f"IO error saving file: {str(e)}")
        raise

    return file_path


# ================================ Ping 工具 ================================


# Ping 辅助类
class PingHelper:

    # 执行 Ping 命令（仅 Windows）
    @Platform.system(Platform.Window)
    def ping(url: str = "www.baidu.com www.google.com", count: int = 65535, interval: int = 0, view: str = "point") -> None:
        import re

        # 解析目标地址
        def parse_targets(url: str) -> List[str]:
            if not url:
                raise ValueError("url not empty")

            targets = re.split(r"[,\s]+", url.strip())
            targets = list(filter(None, targets))

            # 处理协议前缀，提取主机名
            processed_targets = []
            for target in targets:
                if target.startswith(("http://", "https://")):
                    parsed = urlparse(target)
                    if parsed.hostname:
                        processed_targets.append(parsed.hostname)
                else:
                    processed_targets.append(target)

            # 去重
            processed_targets = list(dict.fromkeys(processed_targets))

            if not processed_targets:
                raise ValueError("no valid target was resolved.")

            return processed_targets

        # 解析地址
        targets = parse_targets(url)
        # 执行程序
        program_exec = os.path.join(os.getcwd(), "static/resource/nping/nping.exe")
        # 构建命令
        cmd = [program_exec, *targets, "-c", str(count), "-i", str(interval), "-v", view]
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)


# ================================ IP 信息 ================================


# IP 信息辅助类
class IPInfoHelper:

    def __init__(self, url: str = "https://ipinfo.io/json", timeout: int = 3, fallback_country: str = "CN") -> None:
        self.url = url
        self.timeout = timeout
        self.fallback_country = fallback_country
        self.data: Optional[Dict[str, str]] = None

    # 获取 IP 信息
    def fetch(self) -> Dict[str, str]:
        try:
            response = requests.get(self.url, timeout=self.timeout)
            if response.status_code == 200:
                self.data = response.json()
            else:
                self.data = {"country": self.fallback_country}
        except requests.exceptions.RequestException:
            self.data = {"country": self.fallback_country}
        return self.data

    # 获取国家代码
    def get_country(self) -> str:
        try:
            return self.data["country"]
        except (KeyError, TypeError) as e:
            logger.error(f"Error: {str(e)}")
            return "CN"

    # 判断是否为中国地区
    def is_china(self) -> bool:
        if not self.data:
            self.fetch()
        return self.data.get("country") == "CN"


# ================================ 代理工具 ================================


# 代理辅助类
class ProxyHelper:

    def __init__(
        self,
        protocol: BaseAbstractEnum.Protocol = BaseAbstractEnum.Protocol.HTTP,
        ip: str = "127.0.0.1",
        port: int = 10808,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.protocol = protocol.value.lower()
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password

    # 构造代理 URL
    def _build_url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.ip}:{self.port}"
        else:
            return f"{self.protocol}://{self.ip}:{self.port}"

    # 获取代理字典
    def get_proxies(self) -> Dict[str, str]:
        proxy = self._build_url()
        return {"http": proxy, "https": proxy}

    # 设置环境变量
    def set_env(self) -> None:
        if self.protocol.startswith("socks"):
            raise ValueError("environment variables do not support SOCKS proxy. Please use an HTTP proxy or the get_proxies() method instead.")
        proxy_url = self._build_url()
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url

    # 清除环境变量
    def clear_env(self) -> None:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)

    # 验证代理连接
    def verify(self, url: str = "https://www.google.com", timeout: int = 1, print_log: bool = True) -> bool:
        return verify_connection(url, proxy=self.get_proxies(), timeout=timeout, show_print=print_log)


# 启动代理
def start_proxy(enable: bool = False) -> None:
    import urllib.request

    proxies = urllib.request.getproxies()
    # 软件代理设置
    if enable:
        proxy = ProxyHelper()
        is_proxy_verify = proxy.verify(timeout=2, print_log=False)
        if is_proxy_verify:
            proxy.set_env()
            logger.info("Proxy enabled and verified successfully.")
        else:
            logger.warning("Proxy verification failed. Please check your proxy settings.")
    # 获取系统代理
    elif len(proxies) > 0:
        os.environ["HTTP_PROXY"] = proxies.get("http", "")
        os.environ["HTTPS_PROXY"] = proxies.get("https", "")
        logger.info("Use system proxy.")


# ================================ 调用示例 ================================


if __name__ == "__main__":

    print(get_localhost())
    print(NetUtil.local_ipv4s())

    url = "https://www.google.com"
    print(verify_connection(url, timeout=1))

    # ==================== 代理示例 ====================

    proxy = ProxyHelper()
    print(proxy.verify(url))

    proxy = ProxyHelper(BaseAbstractEnum.Protocol.SOCKS5, "127.0.0.1", 10808)
    print(proxy.verify(url))

    # ==================== 代理认证示例 ====================

    username = "admin"
    password = "123456"
    proxy = ProxyHelper(BaseAbstractEnum.Protocol.HTTP, "127.0.0.1", 10810, username, password)
    print(proxy.verify(url))

    # ==================== 环境变量示例 ====================

    proxy = ProxyHelper(BaseAbstractEnum.Protocol.HTTP, "127.0.0.1", 10808)
    proxy.set_env()
    response = requests.get("https://www.google.com", timeout=5)
    print(response.status_code)
