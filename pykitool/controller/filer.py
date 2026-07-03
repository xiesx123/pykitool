import os
import sys

sys.path.insert(0, os.getcwd())
import shutil
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

from pykitool.base.result import R, Result
from pykitool.controller.exce import RuntimeException
from pykitool.utils import cbfile


def register_controller_filer(
    app: FastAPI,
    *,
    prefix: str = "/file",
    tags: list[str] | None,
    upload_dir: str = "upload",
    download_dir: str = "download",
) -> None:
    """
    注册文件上传/下载路由，提供两个接口：

    - ``POST {prefix}/upload``   — 上传文件，保存至 ``upload_dir``，返回文件路径与 MD5
    - ``GET  {prefix}/download`` — 下载文件，路径限制在 ``download_dir`` 内，防止路径遍历

    Args:
        app:          FastAPI 实例
        prefix:       路由前缀，默认 ``"/file"``
        tags:         Swagger 标签列表
        upload_dir:   上传文件保存目录，默认 ``"upload"``；可通过表单字段 ``path`` 覆盖
        download_dir: 下载文件根目录，默认 ``"download"``；只允许访问该目录内的文件

    示例::

        from fastapi import FastAPI
        from pykitool.controller.filer import register_controller_filer

        app = FastAPI()

        # 最简注册，使用默认目录
        register_controller_filer(app, tags=["file"])

        # 自定义前缀与目录
        register_controller_filer(
            app,
            prefix="/api/file",
            tags=["file"],
            upload_dir="webapp/upload",
            download_dir="webapp/download",
        )

    接口示例::

        # 上传文件（multipart/form-data）
        POST /file/upload
        file=<binary>          # 必填，上传的文件
        path=upload/images     # 可选，覆盖默认上传目录

        # 返回
        {"code": 0, "data": {"path": "/abs/path/to/file.png", "md5": "d41d8cd9..."}}

        # 下载文件
        GET /file/download?path=download/report.pdf
    """
    router = APIRouter()

    # 上传
    @router.post("/upload", response_model=Result)
    def upload(file: UploadFile = File(...), path: str = Form(upload_dir)):
        try:
            # 计算文件的 MD5 值
            file_md5 = cbfile.md5(file.file)
            # 使用 MD5 值和文件扩展名作为新的文件名
            cbfile.mk(path)
            file_location = cbfile.ap(os.path.join(path, file.filename))
            # 重置文件指针
            file.file.seek(0)
            # 将文件保存到指定路径
            with open(file_location, "wb") as f:
                shutil.copyfileobj(file.file, f)
            return R.success(data={"path": file_location, "md5": file_md5})
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            raise RuntimeException(message=str(e))

    # 下载
    @router.get("/download")
    def download(path: str):
        try:
            # 设置基础目录
            base_dir = Path(download_dir).resolve()
            # 提取相对路径
            relative_path = cbfile.relative_path(path, download_dir)
            # 拼接成完整的文件路径
            full_path = base_dir / relative_path
            # 规范化路径，避免路径遍历
            full_path = full_path.resolve()

            # 检查文件是否存在以及是否在允许的目录范围内
            if not full_path.exists() or not full_path.is_file():
                raise HTTPException(status_code=404, detail="File not found")
            if not str(full_path).startswith(str(base_dir)):
                raise HTTPException(status_code=403, detail="Access denied")

            # 返回文件响应
            return FileResponse(
                full_path,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{quote(full_path.name)}",
                },
            )
        except Exception as e:
            logger.error(f"Error downloading file {path}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

    app.include_router(router, prefix=prefix, tags=tags)
