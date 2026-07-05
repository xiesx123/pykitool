from typing import Callable, Optional

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html


def register_controller_swagger(
    app: FastAPI,
    *,
    prefix: str = "",
    auth_callable: Optional[Callable[[], str]] = None,
    openapi_url: str = "/openapi.json",
    swagger_title: str = "Restful API - Swagger UI",
    redoc_title: str = "Restful API - Redoc",
):
    """
    注册 Swagger / Redoc 文档路由，支持可选的自定义认证。

    Args:
        app:           FastAPI 实例
        prefix:        路由前缀，默认为空（即 /docs、/redoc）
        auth_callable: FastAPI 依赖函数，签名为 ``() -> str``，直接作为``Depends(auth_callable)`` 注入到文档路由；不传则直接放行，无需任何认证
        openapi_url:   OpenAPI JSON 地址，默认 /openapi.json
        swagger_title: Swagger UI 页面标题
        redoc_title:   Redoc 页面标题

    示例::

        from fastapi import FastAPI
        from pykitool.controller.swagger import register_controller_swagger

        app = FastAPI()

        # 1. 不传 auth_callable，直接可访问
        register_controller_swagger(app)

        # 2. HTTP Basic 认证
        from fastapi import Depends, HTTPException, status
        from fastapi.security import HTTPBasic, HTTPBasicCredentials

        _security = HTTPBasic()

        def basic_auth(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
            if credentials.username != "admin" or credentials.password != "secret":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
            return credentials.username

        register_controller_swagger(app, auth_callable=basic_auth)

        # 3. Bearer Token 认证
        from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

        _bearer = HTTPBearer()

        def token_auth(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
            if credentials.credentials != "my-token":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            return "user"

        register_controller_swagger(app, auth_callable=token_auth)

    """
    if auth_callable is not None:

        @app.get(f"{prefix}/docs", include_in_schema=False)
        async def get_documentation(username: str = Depends(auth_callable)):
            return get_swagger_ui_html(openapi_url=openapi_url, title=swagger_title)

        @app.get(f"{prefix}/redoc", include_in_schema=False)
        async def get_redoc_documentation(username: str = Depends(auth_callable)):
            return get_redoc_html(openapi_url=openapi_url, title=redoc_title)

    else:

        @app.get(f"{prefix}/docs", include_in_schema=False)
        async def get_documentation():
            return get_swagger_ui_html(openapi_url=openapi_url, title=swagger_title)

        @app.get(f"{prefix}/redoc", include_in_schema=False)
        async def get_redoc_documentation():
            return get_redoc_html(openapi_url=openapi_url, title=redoc_title)
