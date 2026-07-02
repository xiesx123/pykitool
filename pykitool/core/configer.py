import os
import sys

sys.path.insert(0, os.getcwd())
from collections.abc import Callable
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Query
from hutool import JSONUtil
from loguru import logger
from pydantic import BaseModel, Field

from pykitool.base.result import R, Result
from pykitool.core.exception import RuntimeException


# 配置更新请求模型（单字段或整段 JSON）
class ConfigUpdateVO(BaseModel):
    path: str = Field(..., description="配置路径，如 site.name 或 site", example="site.name")
    data: Any = Field(..., description="配置值，支持任意类型（传 dict 时自动与现有值浅合并）", example="我的站点")


def register_controller_configer(
    app: FastAPI,
    *,
    prefix: str = "",
    tags: list[str] | None = None,
    path: str,
    reload_handler: Callable[[], None] | None = None,
) -> None:
    """
    注册配置读写路由。

    Args:
        app:       FastAPI 实例
        prefix:    路由前缀，默认为空
        tags:      Swagger 标签
        path:      settings JSON 文件路径，如 "config/settings.json"
        on_reload: 配置写入后的回调，用于刷新项目内存配置，可选

    Example::

        from fastapi import FastAPI
        from pykitool.core.configer import register_controller_configer

        app = FastAPI()
        register_controller_configer(app, prefix="/api", tags=["config"], path="config/settings.json", reload_handler=prefs.reload)
    """
    router = APIRouter()

    # 获取配置
    @router.get("/get", response_model=Result[dict], summary="获取配置")
    def get_config(key: Optional[str] = Query(None, description="配置路径，如 site.name，不传则返回全部配置")):
        try:
            data = JSONUtil.read_json_object(path)
            if key:
                return R.success(data={key: JSONUtil.get_by_path(data, key)})
            return R.success(data=data)
        except Exception as e:
            logger.error(f"Get config failed: {e}")
            raise RuntimeException(message=f"Get config failed: {e}") from e

    # 更新配置（支持单字段或整段 JSON，传入 dict 时自动与现有值浅合并）
    @router.post("/set", response_model=Result[dict], summary="更新配置")
    def set_config(vo: ConfigUpdateVO):
        try:
            data = JSONUtil.read_json_object(path)
            # 若当前值和新值都是 dict，做浅合并以保留未传字段的原有值
            existing = JSONUtil.get_by_path(data, vo.path)
            if isinstance(existing, dict) and isinstance(vo.data, dict):
                new_val = {**existing, **vo.data}
            else:
                new_val = vo.data
            JSONUtil.put_by_path(data, vo.path, new_val)
            JSONUtil.write_json(path, data, indent=2)
            logger.info(f"Config updated: {vo.path}")
            if reload_handler:
                reload_handler()
            updated_value = JSONUtil.get_by_path(data, vo.path)
            return R.success(data={vo.path: updated_value}, message="Config updated successfully")
        except Exception as e:
            logger.error(f"Update config failed: {e}")
            raise RuntimeException(message=f"Update config failed: {e}") from e

    app.include_router(router, prefix=prefix, tags=tags)
