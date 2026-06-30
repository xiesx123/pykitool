import json
import time
from functools import wraps
from typing import Any, Callable, List, Optional

import requests
from loguru import logger

from pykitool.utils import cbexecutor


class Grafana:
    """
    Grafana Graphite Metrics 客户端，支持实例化配置，可供外部项目直接使用。

    Usage::

        from pykitool.support.grafana import Grafana

        grafana = Grafana(
            api_uid="your_uid",
            api_token="your_token",
            api_name="your_app",
            api_url="https://graphite-prod-36-prod-us-west-0.grafana.net/graphite/metrics",
            tag_provider=lambda: [f"version={APP_VERSION}", f"debug={is_debug()}"],
        )

        # 作为装饰器
        @grafana.metric
        def my_func():
            ...

        # 手动发送
        data = grafana.build_metric(tags=["env=prod"])
        grafana.send_metric([data])
    """

    def __init__(
        self,
        api_uid: str,
        api_token: str,
        app_name: str = "app",
        api_url: str = "https://graphite-prod-36-prod-us-west-0.grafana.net/graphite/metrics",
        tags: Optional[Callable[[], List[str]]] = None,
    ) -> None:
        """
        初始化 Grafana 客户端。

        :param api_uid:       Grafana API User ID
        :param api_url:       Graphite Metrics 推送地址
        :param api_token:     Grafana API Token
        :param name:          Metric 名称（默认 "app"）
        :param tags:  额外标签 tags 列表，例如 lambda: ["version=1.0", "debug=false"]
        """
        self.api_uid = api_uid
        self.api_url = api_url
        self.api_token = api_token
        self.name = app_name
        self.tags = tags

    # 装饰器：监控函数执行（fire-and-forget，不阻塞主线程）
    def metric(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            finally:
                list = [f"func={func.__name__}"]
                if self.tags is not None:
                    try:
                        list += self.tags()
                    except Exception as e:
                        logger.warning(f"Grafana tag_provider error: {e}")
                data = self.build_metric(tags=list)
                cbexecutor.submit(self.send_metric, [data])

        return wrapper

    # 构建监控指标
    def build_metric(self, name: Optional[str] = None, value: float = 1.0, interval: int = -1, tags: List[str] = []) -> dict:
        return {
            "name": name or self.name,
            "value": value,
            "interval": interval,
            "tags": tags,
            "time": int(time.time()),
        }

    # 发送监控指标到 Grafana
    def send_metric(self, metrics: List[dict]) -> dict:
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_uid}:{self.api_token}",
                },
                data=json.dumps(metrics),
            )
            data = response.json()
            logger.trace(f"Grafana response: {data}")
            return data
        except json.JSONDecodeError:
            return {"code": response.status_code, "message": "Invalid JSON response", "data": response.text}
        except Exception as e:
            return {"code": -1, "message": str(e), "data": None}
