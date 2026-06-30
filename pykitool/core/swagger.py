from typing import Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.security import HTTPBasic, HTTPBasicCredentials


def register_controller_swagger(
    app: FastAPI,
    *,
    prefix: str = "",
    auth_handler: Optional[Callable[[str, str], bool]] = None,
    openapi_url: str = "/openapi.json",
    swagger_title: str = "Restful API Documentation - Swagger UI",
    redoc_title: str = "Restful API Documentation - Redoc",
):
    """
    注册 Swagger / Redoc 文档路由，支持可选的 HTTP Basic 验证。

    Args:
        app:           FastAPI 实例
        prefix:        路由前缀，默认为空（即 /docs、/redoc）
        auth_handler:  自定义验证函数，签名为 (username: str, password: str) -> bool
                       不传则直接放行，无需任何认证
        openapi_url:   OpenAPI JSON 地址，默认 /openapi.json
        swagger_title: Swagger UI 页面标题
        redoc_title:   Redoc 页面标题

    Example::

        # 不传 auth_handler，直接可访问
        register_controller_swagger(app)

        # 自定义验证，启用 Basic Auth
        def my_auth(username: str, password: str) -> bool:
            return username == "admin" and password == "secret"

        register_controller_swagger(app, auth_handler=my_auth)

        register_controller_swagger(app, auth_handler=lambda u, p: u == "admin" and p == "secret")

    """
    if auth_handler is not None:
        _security = HTTPBasic()

        def _get_auth(credentials: HTTPBasicCredentials = Depends(_security)):
            if not auth_handler(credentials.username, credentials.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Basic"},
                )
            return credentials.username

        @app.get(f"{prefix}/docs", include_in_schema=False)
        async def get_documentation(username: str = Depends(_get_auth)):
            return get_swagger_ui_html(openapi_url=openapi_url, title=swagger_title)

        @app.get(f"{prefix}/redoc", include_in_schema=False)
        async def get_redoc_documentation(username: str = Depends(_get_auth)):
            return get_redoc_html(openapi_url=openapi_url, title=redoc_title)

    else:

        @app.get(f"{prefix}/docs", include_in_schema=False)
        async def get_documentation():
            return get_swagger_ui_html(openapi_url=openapi_url, title=swagger_title)

        @app.get(f"{prefix}/redoc", include_in_schema=False)
        async def get_redoc_documentation():
            return get_redoc_html(openapi_url=openapi_url, title=redoc_title)
