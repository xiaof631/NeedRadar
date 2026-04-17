"""RSS 源相关的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime

from app.models.rss import FetchStatus, SourceStatus, SourceType
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, PositiveInt


class RssSourceBase(BaseModel):
    """RSS 源公共字段。"""

    name: str = Field(..., max_length=255)
    url: AnyHttpUrl = Field(..., description="RSS 源地址")
    category: str | None = Field(default=None, max_length=255)
    frequency: PositiveInt = Field(default=3600, description="抓取频率（秒）")
    source_type: SourceType = Field(default=SourceType.RSS, description="数据源类型")
    config: dict[str, str | int | float | bool | None] = Field(
        default={},
        description="适配器专属配置",
    )


class RssSourceCreate(RssSourceBase):
    """创建 RSS 源的输入模型。"""

    status: SourceStatus = Field(default=SourceStatus.ACTIVE)


class RssSourceUpdate(BaseModel):
    """更新 RSS 源的输入模型。"""

    name: str | None = Field(default=None, max_length=255)
    url: AnyHttpUrl | None = Field(default=None)
    category: str | None = Field(default=None, max_length=255)
    frequency: PositiveInt | None = Field(default=None)
    source_type: SourceType | None = Field(default=None)
    config: dict[str, str | int | float | bool | None] | None = Field(default=None)
    status: SourceStatus | None = Field(default=None)


class RssSourceRead(RssSourceBase):
    """RSS 源的输出模型。"""

    id: int
    status: SourceStatus
    last_fetched_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RssSourceList(BaseModel):
    """RSS 源分页列表响应。"""

    total: int
    items: list[RssSourceRead]


class FetchLogRead(BaseModel):
    """RSS 抓取日志输出模型。"""

    id: int
    source_id: int
    fetched_at: datetime
    status: FetchStatus
    http_status: int | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FetchLogList(BaseModel):
    """抓取日志列表响应。"""

    total: int
    items: list[FetchLogRead]


class FetchResultRead(BaseModel):
    """手动触发抓取的结果。"""

    source_id: int
    fetched_entries: int
    new_entries: int
    status: FetchStatus
    error_message: str | None = None
