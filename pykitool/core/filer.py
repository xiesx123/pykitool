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
from pykitool.core.exception import RuntimeException
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
    注册文件上传/下载路由。

    Args:
        app:        FastAPI 实例
        prefix:     路由前缀，默认 /file
        upload_dir: 默认上传目录，默认 "upload"
        base_dir:   下载文件的根目录，默认 "webapp"

    Example::

        from fastapi import FastAPI
        from pykitool.core.filer import register_controller_filer

        app = FastAPI()
        register_controller_filer(app)
        # 自定义配置
        register_controller_filer(app, prefix="/api/file", upload_dir="webapp/upload", download_dir="webapp/download")
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
