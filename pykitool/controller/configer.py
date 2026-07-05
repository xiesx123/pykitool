import os
import sys

sys.path.insert(0, os.getcwd())
from collections.abc import Callable
from typing import Any, Optional

from fastapi import APIRouter, Depends, FastAPI, Query
from hutool import JSONUtil
from loguru import logger
from pydantic import BaseModel, Field

from pykitool.base.result import R, Result
from pykitool.controller.exce import RuntimeException


# 配置更新请求模型（单字段或整段 JSON）
class ConfigVO(BaseModel):
    """
    配置更新请求体模型。

    Attributes:
        path: 配置路径，支持点号分隔的嵌套路径，如 ``"site.name"`` 或顶层键 ``"site"``
        data: 配置值，支持任意类型；传入 dict 时会与现有值做浅合并，保留未传字段

    示例:

        # 更新单个字段
        vo = ConfigVO(path="site.name", data="我的站点")

        # 更新整个嵌套对象（浅合并，只更新传入的键）
        vo = ConfigVO(path="site", data={"name": "新名称", "logo": "logo.png"})
    """

    path: str = Field(..., description="配置路径，如 site.name 或 site", example="site.name")
    data: Any = Field(..., description="配置值，支持任意类型（传 dict 时自动与现有值浅合并）", example="我的站点")


def register_controller_configer(
    app: FastAPI,
    *,
    prefix: str = "",
    tags: list[str] | None = None,
    path: str,
    listener: Callable[[], None] | None = None,
    auth_read_callable: Callable[[], str] | None = None,
    auth_write_callable: Callable[[], str] | None = None,
) -> None:
    """
    注册配置读写路由，提供两个接口：

    - ``GET  {prefix}/get``  — 读取配置，可选 ``key`` 参数指定路径，不传则返回全部配置
    - ``POST {prefix}/set``  — 更新配置，请求体为 ``ConfigVO``，dict 值自动浅合并

    Args:
        app:           FastAPI 实例
        prefix:        路由前缀，默认为空
        tags:          Swagger 标签列表
        path:          settings JSON 文件路径，如 ``"config/settings.json"``
        listener:      配置写入后的回调，用于刷新项目内存配置，可选
        auth_callable: FastAPI 依赖函数，签名为 ``() -> str``，直接作为
                       ``Depends(auth_callable)`` 注入到所有路由；
                       不传则所有接口开放访问

    示例::

        from fastapi import FastAPI
        from pykitool.controller.configer import register_controller_configer

        app = FastAPI()

        # 1. 最简注册（无认证，无热重载）
        register_controller_configer(app, path="config/settings.json")

        # 2. 携带热重载回调
        register_controller_configer(
            app,
            path="config/settings.json",
            listener=prefs.reload,
        )

        # 3. HTTP Basic 认证
        from fastapi import Depends, HTTPException, status
        from fastapi.security import HTTPBasic, HTTPBasicCredentials

        _security = HTTPBasic()

        def basic_auth(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
            if credentials.username != "admin" or credentials.password != "secret":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
            return credentials.username

        register_controller_configer(
            app,
            prefix="/api",
            tags=["config"],
            path="config/settings.json",
            listener=prefs.reload,
            auth_callable=basic_auth,
        )

        # 4. Bearer Token 认证
        from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

        _bearer = HTTPBearer()

        def token_auth(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
            if credentials.credentials != "my-token":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            return "user"

        register_controller_configer(
            app,
            path="config/settings.json",
            auth_callable=token_auth,
        )

    接口说明::

        GET  {prefix}/get          — 返回全部配置
        GET  {prefix}/get?key=x.y  — 返回指定路径的值
        POST {prefix}/set          — 更新配置，Body: {"path": "x.y", "data": <value>}
    """
    router = APIRouter()

    # 可选认证依赖：用户自定义 auth_callable 直接作为 Depends 注入
    _read_deps = [Depends(auth_read_callable)] if auth_read_callable is not None else []
    _write_deps = [Depends(auth_write_callable)] if auth_write_callable is not None else []

    # 获取配置
    @router.get("/get", response_model=Result[dict], summary="获取配置", dependencies=_read_deps)
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
    @router.post("/set", response_model=Result[dict], summary="更新配置", dependencies=_write_deps)
    def set_config(vo: ConfigVO):
        try:
            data = JSONUtil.read_json_object(path)
            existing = JSONUtil.get_by_path(data, vo.path)
            if isinstance(existing, dict) and isinstance(vo.data, dict):
                new_val = {**existing, **vo.data}
            else:
                new_val = vo.data
            JSONUtil.put_by_path(data, vo.path, new_val)
            JSONUtil.write_json(path, data, indent=2)
            logger.info(f"Config updated: {vo.path}")
            if listener:
                listener()
            updated_value = JSONUtil.get_by_path(data, vo.path)
            return R.success(data={vo.path: updated_value}, message="Config updated successfully")
        except Exception as e:
            logger.error(f"Update config failed: {e}")
            raise RuntimeException(message=f"Update config failed: {e}") from e

    app.include_router(router, prefix=prefix, tags=tags)
