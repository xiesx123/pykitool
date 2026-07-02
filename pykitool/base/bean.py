from typing import List, Optional

from pydantic import BaseModel, Field


# 分页查询请求
class PageVO(BaseModel):
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="关键词")


# 批量启用/禁用请求
class BatchEnableVO(BaseModel):
    ids: List[str] = Field(..., description="ID列表")
    enable: bool = Field(..., description="true=启用，false=禁用")


# 批量状态请求
class BatchStatusVO(BaseModel):
    ids: List[int] = Field(..., description="ID列表")
    status: int = Field(..., description="状态")


# 批量删除请求
class BatchDeleteVO(BaseModel):
    ids: List[str] = Field(..., description="ID列表")


# 批量操作响应
class RowsResponse(BaseModel):
    rows: int = Field(..., description="受影响的用户数量")
