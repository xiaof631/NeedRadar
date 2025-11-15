"""筛选规则管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import FilterRuleCreate, FilterRuleList, FilterRuleRead, FilterRuleUpdate
from app.services import filter_rules

router = APIRouter(prefix="/filter-rules", tags=["Filter Rules"])


@router.get("/", response_model=FilterRuleList, summary="列出筛选规则")
async def list_filter_rules(
    skip: int = Query(default=0, ge=0, description="跳过的记录数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回的记录数量"),
    enabled: bool | None = Query(default=None, description="按启用状态过滤"),
    search: str | None = Query(default=None, description="名称或描述搜索"),
) -> FilterRuleList:
    total, items = filter_rules.list_rules(
        skip=skip,
        limit=limit,
        enabled=enabled,
        search=search,
    )
    return FilterRuleList(total=total, items=[FilterRuleRead.model_validate(item) for item in items])


@router.post(
    "/",
    response_model=FilterRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建筛选规则",
)
async def create_filter_rule(payload: FilterRuleCreate) -> FilterRuleRead:
    rule = filter_rules.create_rule(payload.model_dump())
    return FilterRuleRead.model_validate(rule)


@router.get("/{rule_id}", response_model=FilterRuleRead, summary="获取筛选规则详情")
async def get_filter_rule(rule_id: int) -> FilterRuleRead:
    try:
        rule = filter_rules.get_rule(rule_id)
    except filter_rules.FilterRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="筛选规则不存在") from exc
    return FilterRuleRead.model_validate(rule)


@router.put("/{rule_id}", response_model=FilterRuleRead, summary="更新筛选规则")
async def update_filter_rule(rule_id: int, payload: FilterRuleUpdate) -> FilterRuleRead:
    data = payload.model_dump(exclude_unset=True)
    try:
        rule = filter_rules.update_rule(rule_id, data)
    except filter_rules.FilterRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="筛选规则不存在") from exc
    return FilterRuleRead.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除筛选规则")
async def delete_filter_rule(rule_id: int) -> None:
    try:
        filter_rules.delete_rule(rule_id)
    except filter_rules.FilterRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="筛选规则不存在") from exc
