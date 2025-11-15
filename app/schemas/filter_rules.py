"""筛选规则相关的序列化模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FilterRuleBase(BaseModel):
    """筛选规则的公共字段。"""

    name: str = Field(..., max_length=255, description="规则名称")
    description: str | None = Field(default=None, max_length=1024, description="规则描述")
    keywords: list[str] | None = Field(default=None, description="匹配的关键词集合")
    patterns: list[str] | None = Field(default=None, description="正则表达式集合")
    min_score: float = Field(default=0.5, ge=0.0, le=1.0, description="最低命中得分阈值")


class FilterRuleCreate(FilterRuleBase):
    """创建筛选规则的输入模型。"""

    enabled: bool = Field(default=True, description="是否启用")


class FilterRuleUpdate(BaseModel):
    """更新筛选规则的输入模型。"""

    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    keywords: list[str] | None = Field(default=None)
    patterns: list[str] | None = Field(default=None)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    enabled: bool | None = Field(default=None)


class FilterRuleRead(FilterRuleBase):
    """筛选规则的输出模型。"""

    id: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FilterRuleList(BaseModel):
    """筛选规则分页列表响应。"""

    total: int
    items: list[FilterRuleRead]
