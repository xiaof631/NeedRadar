"""NeedRadar 命令行入口。"""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Annotated, Any

import typer
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models import CandidateNeedStatus, RawEntryStatus, SourceStatus
from app.schemas import CandidateNeedRead, RawEntryRead
from app.services import candidate_needs, filter_rules, raw_entries, rss_sources
from app.services.candidate_needs import CandidateNeedNotFoundError
from app.services.raw_entries import RawEntryNotFoundError

app = typer.Typer(help="NeedRadar 工具集")
logger = get_logger(__name__)

rss_app = typer.Typer(help="RSS 源管理")
entries_app = typer.Typer(help="原始条目管理")
rules_app = typer.Typer(help="筛选规则管理")
candidates_app = typer.Typer(help="候选需求管理")
app.add_typer(rss_app, name="rss")
app.add_typer(entries_app, name="entries")
app.add_typer(rules_app, name="rules")
app.add_typer(candidates_app, name="candidates")


@app.command()
def show_config() -> None:
    """打印当前配置。"""

    settings = get_settings()
    configure_logging()
    logger.info("current-settings", **settings.model_dump())


@app.command()
def init_db() -> None:
    """初始化内存数据库（重置数据）。"""

    rss_sources.reset_storage()
    typer.echo("已重置内存数据库")


@rules_app.command("list")
def list_rules(
    enabled: Annotated[
        bool | None,
        typer.Option("--enabled/--disabled", help="根据启用状态过滤"),
    ] = None,
    search: Annotated[
        str | None,
        typer.Option(help="根据名称或描述搜索"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(help="最大返回数量", min=1, max=100),
    ] = 20,
) -> None:
    """列出筛选规则。"""

    total, items = filter_rules.list_rules(enabled=enabled, search=search, limit=limit)
    if total == 0:
        typer.echo("暂无筛选规则")
        raise typer.Exit()

    typer.echo(f"共 {total} 条规则，当前展示 {len(items)} 条：")
    for rule in items:
        typer.echo(
            f"[{rule.id}] {rule.name} - "
            f"启用: {'是' if rule.enabled else '否'}, 最低得分: {rule.min_score}"
        )


@rules_app.command("create")
def create_rule(
    name: Annotated[str, typer.Argument(help="规则名称")],
    description: Annotated[
        str | None,
        typer.Option(help="规则描述"),
    ] = None,
    keywords: Annotated[
        list[str] | None,
        typer.Option("--keyword", help="匹配关键词，可重复"),
    ] = None,
    patterns: Annotated[
        list[str] | None,
        typer.Option("--pattern", help="匹配正则表达式，可重复"),
    ] = None,
    min_score: Annotated[
        float,
        typer.Option(help="最低命中得分阈值", min=0.0, max=1.0),
    ] = 0.5,
    enabled: Annotated[
        bool,
        typer.Option("--enable/--disable", help="是否启用规则"),
    ] = True,
) -> None:
    """创建新的筛选规则。"""

    rule = filter_rules.create_rule(
        {
            "name": name,
            "description": description,
            "keywords": keywords or [],
            "patterns": patterns or [],
            "min_score": min_score,
            "enabled": enabled,
        }
    )
    typer.echo(f"已创建筛选规则 #{rule.id}: {rule.name}")


@rules_app.command("update")
def update_rule(
    rule_id: Annotated[int, typer.Argument(help="筛选规则 ID")],
    name: Annotated[str | None, typer.Option(help="新的名称")] = None,
    description: Annotated[str | None, typer.Option(help="新的描述")] = None,
    keywords: Annotated[
        list[str] | None,
        typer.Option("--keyword", help="覆盖关键词列表，可重复"),
    ] = None,
    patterns: Annotated[
        list[str] | None,
        typer.Option("--pattern", help="覆盖正则列表，可重复"),
    ] = None,
    min_score: Annotated[
        float | None,
        typer.Option(help="新的最低命中得分阈值", min=0.0, max=1.0),
    ] = None,
    enabled: Annotated[
        bool | None,
        typer.Option("--enable/--disable", help="是否启用"),
    ] = None,
) -> None:
    """更新已有的筛选规则。"""

    payload: dict[str, Any] = {}
    for key, value in {
        "name": name,
        "description": description,
        "min_score": min_score,
        "enabled": enabled,
    }.items():
        if value is not None:
            payload[key] = value
    if keywords is not None:
        payload["keywords"] = keywords
    if patterns is not None:
        payload["patterns"] = patterns

    if not payload:
        typer.echo("无需更新任何字段")
        raise typer.Exit()

    try:
        rule = filter_rules.update_rule(rule_id, payload)
    except filter_rules.FilterRuleNotFoundError as exc:
        raise typer.BadParameter("筛选规则不存在", param_hint="rule_id") from exc

    typer.echo(f"已更新筛选规则 #{rule.id}: {rule.name}")


@rules_app.command("delete")
def delete_rule(rule_id: Annotated[int, typer.Argument(help="筛选规则 ID")]) -> None:
    """删除筛选规则。"""

    try:
        filter_rules.delete_rule(rule_id)
    except filter_rules.FilterRuleNotFoundError as exc:
        raise typer.BadParameter("筛选规则不存在", param_hint="rule_id") from exc

    typer.echo(f"已删除筛选规则 #{rule_id}")


@rss_app.command("list")
def list_sources(
    status: Annotated[
        SourceStatus | None,
        typer.Option(help="根据状态过滤", case_sensitive=False),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option(help="根据分类过滤"),
    ] = None,
) -> None:
    """列出所有 RSS 源。"""

    total, items = rss_sources.list_sources(status=status, category=category)
    if total == 0:
        typer.echo("暂无 RSS 源")
        raise typer.Exit()

    for source in items:
        message = (
            f"[{source.id}] {source.name} - {source.url} "
            f"(分类: {source.category or '-'}, 状态: {source.status})"
        )
        typer.echo(message)


@rss_app.command("create")
def create_source(
    name: Annotated[str, typer.Argument(help="RSS 源名称")],
    url: Annotated[str, typer.Argument(help="RSS 地址")],
    frequency: Annotated[int, typer.Option(help="抓取频率（秒）", min=60)] = 3600,
    category: Annotated[str | None, typer.Option(help="分类标签")] = None,
) -> None:
    """创建新的 RSS 源。"""

    try:
        source = rss_sources.create_source(
            {
                "name": name,
                "url": url,
                "frequency": frequency,
                "category": category,
            }
        )
    except rss_sources.RssSourceAlreadyExistsError as exc:  # pragma: no cover - CLI 提示
        raise typer.BadParameter("RSS 源已存在", param_hint="url") from exc

    typer.echo(f"已创建 RSS 源 #{source.id}: {source.name}")


@rss_app.command("update")
def update_source(
    source_id: Annotated[int, typer.Argument(help="RSS 源 ID")],
    name: Annotated[str | None, typer.Option(help="名称")] = None,
    url: Annotated[str | None, typer.Option(help="RSS 地址")] = None,
    frequency: Annotated[int | None, typer.Option(help="抓取频率（秒）", min=60)] = None,
    category: Annotated[str | None, typer.Option(help="分类标签")] = None,
    status: Annotated[SourceStatus | None, typer.Option(help="状态", case_sensitive=False)] = None,
) -> None:
    """更新 RSS 源信息。"""

    payload = {
        key: value
        for key, value in {
            "name": name,
            "url": url,
            "frequency": frequency,
            "category": category,
            "status": status,
        }.items()
        if value is not None
    }
    if not payload:
        typer.echo("无需更新任何字段")
        raise typer.Exit()

    try:
        source = rss_sources.update_source(source_id, payload)
    except rss_sources.RssSourceNotFoundError as exc:
        raise typer.BadParameter("RSS 源不存在", param_hint="source_id") from exc
    except rss_sources.RssSourceAlreadyExistsError as exc:
        raise typer.BadParameter("RSS 源 URL 已存在", param_hint="url") from exc

    typer.echo(f"已更新 RSS 源 #{source.id}: {source.name}")


@rss_app.command("delete")
def delete_source(source_id: Annotated[int, typer.Argument(help="RSS 源 ID")]) -> None:
    """删除指定的 RSS 源。"""

    try:
        rss_sources.delete_source(source_id)
    except rss_sources.RssSourceNotFoundError as exc:
        raise typer.BadParameter("RSS 源不存在", param_hint="source_id") from exc

    typer.echo(f"已删除 RSS 源 #{source_id}")


@entries_app.command("list")
def list_raw_entries(
    source_id: Annotated[int | None, typer.Option(help="按数据源过滤")] = None,
    status: Annotated[
        RawEntryStatus | None,
        typer.Option(help="按状态过滤", case_sensitive=False),
    ] = None,
    search: Annotated[str | None, typer.Option(help="关键字搜索")] = None,
    limit: Annotated[int, typer.Option(help="显示的最大条目数", min=1, max=100)] = 20,
) -> None:
    """查看原始条目列表。"""

    total, items = raw_entries.list_entries(
        source_id=source_id,
        status=status,
        search=search,
        limit=limit,
    )
    if total == 0:
        typer.echo("暂无原始条目")
        raise typer.Exit()

    typer.echo(f"共 {total} 条，当前展示 {len(items)} 条：")
    for entry in items:
        typer.echo(
            f"[{entry.id}] {entry.title} (来源 #{entry.source_id}, 状态: {entry.status})"
        )


@entries_app.command("update-status")
def update_raw_entry_status(
    entry_id: Annotated[int, typer.Argument(help="原始条目 ID")],
    status: Annotated[RawEntryStatus, typer.Argument(help="新的状态", case_sensitive=False)],
) -> None:
    """更新单条原始条目的状态。"""

    try:
        entry = raw_entries.update_entry_status(entry_id, status)
    except raw_entries.RawEntryNotFoundError as exc:
        raise typer.BadParameter("原始条目不存在", param_hint="entry_id") from exc

    typer.echo(f"已将条目 #{entry.id} 状态更新为 {entry.status}")


@entries_app.command("bulk-status")
def bulk_update_raw_entry_status(
    status: Annotated[RawEntryStatus, typer.Argument(help="新的状态", case_sensitive=False)],
    entry_ids: Annotated[
        list[int],
        typer.Argument(help="需要更新的条目 ID", metavar="ENTRY_ID..."),
    ],
) -> None:
    """批量更新原始条目的状态。"""

    try:
        entries = raw_entries.bulk_update_status(entry_ids, status)
    except raw_entries.RawEntryNotFoundError as exc:
        raise typer.BadParameter("存在不存在的条目", param_hint="entry_ids") from exc

    typer.echo(f"已更新 {len(entries)} 条记录为 {status.value}")


@entries_app.command("export")
def export_raw_entries(
    format: Annotated[
        str,
        typer.Option("--format", help="导出格式", case_sensitive=False),
    ] = "json",
    output: Annotated[Path | None, typer.Option("--output", help="输出文件路径")] = None,
    source_id: Annotated[int | None, typer.Option(help="按数据源过滤")] = None,
    status: Annotated[
        RawEntryStatus | None,
        typer.Option(help="按状态过滤", case_sensitive=False),
    ] = None,
    search: Annotated[str | None, typer.Option(help="关键字搜索")] = None,
    limit: Annotated[int | None, typer.Option(help="最大导出数量", min=1, max=1000)] = None,
) -> None:
    """导出原始条目为 JSON 或 CSV。"""

    fmt = format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("format 必须为 json 或 csv", param_hint="format")

    entries = raw_entries.export_entries(
        source_id=source_id,
        status=status,
        search=search,
        limit=limit,
    )
    models = [RawEntryRead.model_validate(entry) for entry in entries]

    if fmt == "json":
        content = json.dumps(
            [model.model_dump(mode="json") for model in models],
            ensure_ascii=False,
            indent=2,
        )
    else:
        buffer = StringIO()
        fieldnames = [
            "id",
            "source_id",
            "guid",
            "title",
            "summary",
            "content",
            "link",
            "published_at",
            "author",
            "tags",
            "status",
            "created_at",
            "updated_at",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for model in models:
            writer.writerow(
                {
                    "id": model.id,
                    "source_id": model.source_id,
                    "guid": model.guid,
                    "title": model.title,
                    "summary": model.summary or "",
                    "content": model.content or "",
                    "link": model.link or "",
                    "published_at": model.published_at.isoformat() if model.published_at else "",
                    "author": model.author or "",
                    "tags": ";".join(model.tags),
                    "status": model.status.value,
                    "created_at": model.created_at.isoformat(),
                    "updated_at": model.updated_at.isoformat(),
                }
            )
        content = buffer.getvalue()

    if output is not None:
        output.write_text(content, encoding="utf-8")
        typer.echo(f"已导出 {len(models)} 条记录到 {output}")
    else:
        typer.echo(content)


@candidates_app.command("list")
def list_candidate_needs(
    statuses: Annotated[
        list[CandidateNeedStatus] | None,
        typer.Option("--status", help="按状态过滤，可重复", case_sensitive=False),
    ] = None,
    search: Annotated[str | None, typer.Option(help="关键字搜索")] = None,
    raw_entry_id: Annotated[int | None, typer.Option(help="原始条目 ID 过滤")] = None,
    limit: Annotated[int, typer.Option(help="显示的最大条目数", min=1, max=100)] = 20,
) -> None:
    """列出候选需求。"""

    total, items = candidate_needs.list_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        limit=limit,
    )
    if total == 0:
        typer.echo("暂无候选需求")
        raise typer.Exit()

    typer.echo(f"共 {total} 条候选需求，当前展示 {len(items)} 条：")
    for need in items:
        typer.echo(
            f"[{need.id}] {need.summary} (原始条目 #{need.raw_entry_id}, 状态: {need.status.value})"
        )


@candidates_app.command("create")
def create_candidate_need(
    raw_entry_id: Annotated[int, typer.Argument(help="关联的原始条目 ID")],
    summary: Annotated[str, typer.Argument(help="需求摘要")],
    problem_statement: Annotated[str | None, typer.Option(help="问题描述")] = None,
    target_users: Annotated[str | None, typer.Option(help="目标用户")] = None,
    value_proposition: Annotated[str | None, typer.Option(help="价值主张")] = None,
    competition: Annotated[str | None, typer.Option(help="竞争情况")] = None,
    confidence: Annotated[
        float | None,
        typer.Option(help="信心指数", min=0.0, max=1.0),
    ] = None,
    status: Annotated[
        CandidateNeedStatus,
        typer.Option("--status", help="初始状态", case_sensitive=False),
    ] = CandidateNeedStatus.PENDING_REVIEW,
    notes: Annotated[str | None, typer.Option(help="备注")] = None,
) -> None:
    """创建候选需求。"""

    try:
        need = candidate_needs.create_need(
            {
                "raw_entry_id": raw_entry_id,
                "summary": summary,
                "problem_statement": problem_statement,
                "target_users": target_users,
                "value_proposition": value_proposition,
                "competition": competition,
                "confidence": confidence,
                "status": status,
                "notes": notes,
            }
        )
    except RawEntryNotFoundError as exc:
        raise typer.BadParameter("关联的原始条目不存在", param_hint="raw_entry_id") from exc

    typer.echo(f"已创建候选需求 #{need.id}: {need.summary}")


@candidates_app.command("update")
def update_candidate_need(
    need_id: Annotated[int, typer.Argument(help="候选需求 ID")],
    summary: Annotated[str | None, typer.Option(help="新的摘要")] = None,
    problem_statement: Annotated[str | None, typer.Option(help="新的问题描述")] = None,
    target_users: Annotated[str | None, typer.Option(help="新的目标用户")] = None,
    value_proposition: Annotated[str | None, typer.Option(help="新的价值主张")] = None,
    competition: Annotated[str | None, typer.Option(help="新的竞争情况")] = None,
    confidence: Annotated[
        float | None,
        typer.Option(help="新的信心指数", min=0.0, max=1.0),
    ] = None,
    status: Annotated[
        CandidateNeedStatus | None,
        typer.Option("--status", help="更新状态", case_sensitive=False),
    ] = None,
    notes: Annotated[str | None, typer.Option(help="新的备注")] = None,
    raw_entry_id: Annotated[int | None, typer.Option(help="新的原始条目 ID")] = None,
) -> None:
    """更新候选需求信息。"""

    payload: dict[str, Any] = {
        key: value
        for key, value in {
            "summary": summary,
            "problem_statement": problem_statement,
            "target_users": target_users,
            "value_proposition": value_proposition,
            "competition": competition,
            "confidence": confidence,
            "status": status,
            "notes": notes,
            "raw_entry_id": raw_entry_id,
        }.items()
        if value is not None
    }
    if not payload:
        typer.echo("无需更新任何字段")
        raise typer.Exit()

    try:
        need = candidate_needs.update_need(need_id, payload)
    except CandidateNeedNotFoundError as exc:
        raise typer.BadParameter("候选需求不存在", param_hint="need_id") from exc
    except RawEntryNotFoundError as exc:
        raise typer.BadParameter("关联的原始条目不存在", param_hint="raw_entry_id") from exc

    typer.echo(f"已更新候选需求 #{need.id}")


@candidates_app.command("update-status")
def update_candidate_need_status(
    need_id: Annotated[int, typer.Argument(help="候选需求 ID")],
    status: Annotated[CandidateNeedStatus, typer.Argument(help="新的状态", case_sensitive=False)],
) -> None:
    """更新候选需求的状态。"""

    try:
        need = candidate_needs.update_need_status(need_id, status)
    except CandidateNeedNotFoundError as exc:
        raise typer.BadParameter("候选需求不存在", param_hint="need_id") from exc

    typer.echo(f"已将候选需求 #{need.id} 状态更新为 {need.status.value}")


@candidates_app.command("export")
def export_candidate_needs(
    format: Annotated[
        str,
        typer.Option("--format", help="导出格式", case_sensitive=False),
    ] = "json",
    output: Annotated[Path | None, typer.Option("--output", help="输出文件路径")] = None,
    statuses: Annotated[
        list[CandidateNeedStatus] | None,
        typer.Option("--status", help="按状态过滤，可重复", case_sensitive=False),
    ] = None,
    search: Annotated[str | None, typer.Option(help="关键字搜索")] = None,
    raw_entry_id: Annotated[int | None, typer.Option(help="原始条目 ID 过滤")] = None,
    limit: Annotated[int | None, typer.Option(help="最大导出数量", min=1, max=1000)] = None,
) -> None:
    """导出候选需求。"""

    fmt = format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("format 必须为 json 或 csv", param_hint="format")

    needs = candidate_needs.export_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        limit=limit,
    )
    models = [CandidateNeedRead.model_validate(need) for need in needs]

    if fmt == "json":
        content = json.dumps(
            [model.model_dump(mode="json") for model in models],
            ensure_ascii=False,
            indent=2,
        )
    else:
        buffer = StringIO()
        fieldnames = [
            "id",
            "raw_entry_id",
            "summary",
            "problem_statement",
            "target_users",
            "value_proposition",
            "competition",
            "confidence",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for model in models:
            writer.writerow(
                {
                    "id": model.id,
                    "raw_entry_id": model.raw_entry_id,
                    "summary": model.summary,
                    "problem_statement": model.problem_statement or "",
                    "target_users": model.target_users or "",
                    "value_proposition": model.value_proposition or "",
                    "competition": model.competition or "",
                    "confidence": model.confidence if model.confidence is not None else "",
                    "status": model.status.value,
                    "notes": model.notes or "",
                    "created_at": model.created_at.isoformat(),
                    "updated_at": model.updated_at.isoformat(),
                }
            )
        content = buffer.getvalue()

    if output is not None:
        output.write_text(content, encoding="utf-8")
        typer.echo(f"已导出 {len(models)} 条候选需求到 {output}")
    else:
        typer.echo(content)


if __name__ == "__main__":
    app()
