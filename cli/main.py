"""NeedRadar 命令行入口。"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Annotated, Any

import typer
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models import (
    CandidateNeedStatus,
    FetchStatus,
    RawEntryStatus,
    SourceStatus,
    SourceType,
    SyncChannel,
)
from app.schemas import CandidateNeedRead, RawEntryRead
import app.services.export_jobs as export_jobs

from app.services import (
    candidate_needs,
    fetch_logs,
    filter_engine,
    filter_rules,
    marketplace_leads,
    pipeline,
    raw_entries,
    rss_sources,
    source_catalog,
    sync_audit,
)
from app.services.candidate_needs import (
    CandidateNeedNotFoundError,
    InvalidStatusTransitionError,
)
from app.services.export_jobs import ExportJobNotFoundError
from app.services.pipeline import CandidateAlreadyExistsError, EntryNotQualifiedError
from app.services.raw_entries import RawEntryNotFoundError
from jobs import task_queue

app = typer.Typer(help="NeedRadar 工具集")
logger = get_logger(__name__)

rss_app = typer.Typer(help="RSS 源管理")
entries_app = typer.Typer(help="原始条目管理")
rules_app = typer.Typer(help="筛选规则管理")
candidates_app = typer.Typer(help="候选需求管理")
marketplace_app = typer.Typer(help="外包项目线索管理")
app.add_typer(rss_app, name="rss")
app.add_typer(entries_app, name="entries")
app.add_typer(rules_app, name="rules")
app.add_typer(candidates_app, name="candidates")
app.add_typer(marketplace_app, name="marketplace")


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


@marketplace_app.command("backfill-outcomes")
def backfill_marketplace_outcomes(
    file: Annotated[Path, typer.Argument(help="CSV 文件路径，需包含 lead_id/outcome/reason_tags/notes 列")],
    reason_separator: Annotated[
        str,
        typer.Option("--reason-separator", help="结果原因标签分隔符"),
    ] = ";",
) -> None:
    """从 CSV 批量回填外包项目线索结果。"""

    if not file.exists():
        raise typer.BadParameter("文件不存在", param_hint="file")

    with file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[marketplace_leads.MarketplaceLeadOutcomeBackfillRow] = []
        for index, record in enumerate(reader, start=2):
            lead_id_raw = (record.get("lead_id") or "").strip()
            if not lead_id_raw:
                raise typer.BadParameter(f"第 {index} 行缺少 lead_id")
            try:
                lead_id = int(lead_id_raw)
            except ValueError as exc:
                raise typer.BadParameter(f"第 {index} 行 lead_id 非法: {lead_id_raw}") from exc

            outcome_raw = (record.get("outcome") or "").strip()
            try:
                outcome = (
                    marketplace_leads.MarketplaceLeadOutcome(outcome_raw)
                    if outcome_raw
                    else None
                )
            except ValueError as exc:
                raise typer.BadParameter(f"第 {index} 行 outcome 非法: {outcome_raw}") from exc

            reason_tags = [
                item.strip()
                for item in (record.get("reason_tags") or "").split(reason_separator)
                if item.strip()
            ]
            notes = (record.get("notes") or "").strip() or None
            rows.append(
                marketplace_leads.MarketplaceLeadOutcomeBackfillRow(
                    lead_id=lead_id,
                    outcome=outcome,
                    reason_tags=reason_tags,
                    notes=notes,
                )
            )

    updated = marketplace_leads.backfill_lead_outcomes(rows)
    typer.echo(f"已回填 {len(updated)} 条 marketplace 线索结果")


@marketplace_app.command("retrospective-report")
def marketplace_retrospective_report(
    output: Annotated[
        Path | None,
        typer.Option("--output", help="输出 Markdown 文件路径；不传则打印到标准输出"),
    ] = None,
) -> None:
    """导出 marketplace 复盘 Markdown。"""

    markdown = marketplace_leads.build_retrospective_markdown()
    if output is None:
        typer.echo(markdown)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown + "\n", encoding="utf-8")
    typer.echo(f"已生成复盘报告：{output}")


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
    source_type: Annotated[
        SourceType | None,
        typer.Option("--source-type", help="根据数据源类型过滤", case_sensitive=False),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option(help="根据分类过滤"),
    ] = None,
) -> None:
    """列出所有 RSS 源。"""

    total, items = rss_sources.list_sources(status=status, source_type=source_type, category=category)
    if total == 0:
        typer.echo("暂无 RSS 源")
        raise typer.Exit()

    for source in items:
        message = (
            f"[{source.id}] {source.name} - {source.url} "
            f"(类型: {source.source_type.value}, 分类: {source.category or '-'}, 状态: {source.status})"
        )
        typer.echo(message)


@rss_app.command("logs")
def list_fetch_logs(
    source_id: Annotated[int | None, typer.Option(help="按数据源过滤")] = None,
    status: Annotated[
        FetchStatus | None,
        typer.Option("--status", help="根据抓取状态过滤", case_sensitive=False),
    ] = None,
    start_fetched_at: Annotated[
        datetime | None,
        typer.Option("--start", help="起始抓取时间 (ISO-8601)"),
    ] = None,
    end_fetched_at: Annotated[
        datetime | None,
        typer.Option("--end", help="结束抓取时间 (ISO-8601)"),
    ] = None,
    skip: Annotated[int, typer.Option(help="跳过的日志数量", min=0)] = 0,
    limit: Annotated[int, typer.Option(help="显示的最大日志数量", min=1, max=100)] = 20,
) -> None:
    """查看 RSS 抓取日志。"""

    total, items = fetch_logs.list_logs(
        source_id=source_id,
        status=status,
        start_fetched_at=start_fetched_at,
        end_fetched_at=end_fetched_at,
        skip=skip,
        limit=limit,
    )
    if total == 0:
        typer.echo("暂无抓取日志")
        raise typer.Exit()

    typer.echo(f"共 {total} 条抓取日志，当前展示 {len(items)} 条：")
    for log in items:
        status_label = "成功" if log.status == FetchStatus.SUCCESS else "失败"
        base = (
            f"[{log.id}] 源 #{log.source_id} - {status_label}"
            f" @ {log.fetched_at.isoformat()}"
        )
        if log.http_status is not None:
            base += f" HTTP {log.http_status}"
        if log.error_message:
            base += f" - {log.error_message}"
        typer.echo(base)


@rss_app.command("create")
def create_source(
    name: Annotated[str, typer.Argument(help="数据源名称")],
    url: Annotated[str, typer.Argument(help="数据源地址")],
    frequency: Annotated[int, typer.Option(help="抓取频率（秒）", min=60)] = 3600,
    category: Annotated[str | None, typer.Option(help="分类标签")] = None,
    source_type: Annotated[
        SourceType,
        typer.Option("--source-type", help="数据源类型", case_sensitive=False),
    ] = SourceType.RSS,
) -> None:
    """创建新的 RSS 源。"""

    try:
        source = rss_sources.create_source(
            {
                "name": name,
                "url": url,
                "frequency": frequency,
                "category": category,
                "source_type": source_type,
            }
        )
    except rss_sources.RssSourceAlreadyExistsError as exc:  # pragma: no cover - CLI 提示
        raise typer.BadParameter("RSS 源已存在", param_hint="url") from exc

    typer.echo(f"已创建 RSS 源 #{source.id}: {source.name}")


@rss_app.command("seed-catalog")
def seed_source_catalog(
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            help="预置数据源目录名称，例如 github-public-expanded / marketplace-public-baseline",
        ),
    ] = "github-public-expanded",
    status: Annotated[
        SourceStatus | None,
        typer.Option(help="可选，覆盖导入后数据源状态", case_sensitive=False),
    ] = None,
) -> None:
    """导入预置数据源目录。"""

    try:
        created, skipped = source_catalog.seed_catalog(profile, status=status)
    except source_catalog.SourceCatalogNotFoundError as exc:
        available = ", ".join(sorted(source_catalog.list_catalogs()))
        raise typer.BadParameter(
            f"未知目录，当前可用: {available}",
            param_hint="profile",
        ) from exc

    typer.echo(
        f"目录 {profile} 导入完成：新增 {len(created)} 个，跳过 {len(skipped)} 个已存在数据源。"
    )
    if created:
        statuses = sorted({source.status.value for source in created})
        typer.echo(f"新增数据源状态: {', '.join(statuses)}")
    for source in created:
        typer.echo(f"  + [{source.id}] {source.name}")


@rss_app.command("update")
def update_source(
    source_id: Annotated[int, typer.Argument(help="数据源 ID")],
    name: Annotated[str | None, typer.Option(help="名称")] = None,
    url: Annotated[str | None, typer.Option(help="数据源地址")] = None,
    frequency: Annotated[int | None, typer.Option(help="抓取频率（秒）", min=60)] = None,
    category: Annotated[str | None, typer.Option(help="分类标签")] = None,
    source_type: Annotated[
        SourceType | None,
        typer.Option("--source-type", help="数据源类型", case_sensitive=False),
    ] = None,
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
            "source_type": source_type,
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


@entries_app.command("evaluate")
def evaluate_raw_entry(
    entry_id: Annotated[int, typer.Argument(help="原始条目 ID")],
    min_score: Annotated[
        float | None,
        typer.Option("--min-score", help="最低得分阈值", min=0.0, max=1.0),
    ] = None,
) -> None:
    """查看指定条目命中的筛选规则与得分。"""

    try:
        entry = raw_entries.get_entry(entry_id)
    except RawEntryNotFoundError as exc:
        raise typer.BadParameter("原始条目不存在", param_hint="entry_id") from exc

    result = filter_engine.evaluate_entry(entry, min_score=min_score)
    if result is None:
        typer.echo("未命中任何启用的筛选规则")
        raise typer.Exit(code=1)

    typer.echo(
        f"命中规则 #{result.rule.id} - {result.rule.name}, 得分 {result.score:.2f}"
    )
    if result.matched_keywords:
        typer.echo("关键词命中: " + ", ".join(result.matched_keywords))
    if result.matched_patterns:
        typer.echo("正则命中: " + ", ".join(result.matched_patterns))


@entries_app.command("promote")
def promote_raw_entry(
    entry_id: Annotated[int, typer.Argument(help="原始条目 ID")],
    min_score: Annotated[
        float | None,
        typer.Option("--min-score", help="最低得分阈值", min=0.0, max=1.0),
    ] = None,
) -> None:
    """自动筛选条目并生成候选需求。"""

    try:
        result = pipeline.promote_entry(entry_id, min_score=min_score)
    except RawEntryNotFoundError as exc:
        raise typer.BadParameter("原始条目不存在", param_hint="entry_id") from exc
    except EntryNotQualifiedError:
        typer.echo("条目未达到筛选阈值，未生成候选需求")
        raise typer.Exit(code=1)
    except CandidateAlreadyExistsError as exc:
        typer.echo(f"条目已存在候选需求 #{exc.need_id}")
        raise typer.Exit(code=1)

    typer.echo(
        f"已生成候选需求 #{result.candidate_need.id}，"
        f"命中规则 #{result.rule_match.rule.id} - {result.rule_match.rule.name}"
    )
    typer.echo(
        f"LLM 信心: {result.structured_need.confidence:.2f}, "
        f"目标用户: {result.structured_need.target_users or '未识别'}"
    )


@entries_app.command("promote-balanced")
def promote_balanced_entries(
    source_types: Annotated[
        list[SourceType],
        typer.Option(
            "--source-type",
            help="限制参与平衡晋升的数据源类型，可重复",
            case_sensitive=False,
        ),
    ] = [SourceType.RSS, SourceType.HACKER_NEWS],
    per_source_type: Annotated[
        int,
        typer.Option("--per-source-type", help="每类来源最多晋升数量", min=1, max=20),
    ] = 3,
    min_score: Annotated[
        float,
        typer.Option("--min-score", help="候选最低得分阈值", min=0.0, max=1.0),
    ] = 0.25,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="仅预览将被晋升的条目"),
    ] = False,
) -> None:
    """按来源配额挑选并晋升一批待处理条目。"""

    ordered_source_types = tuple(dict.fromkeys(source_types))
    previews = pipeline.plan_balanced_promotions(
        source_types=ordered_source_types,
        per_source_type=per_source_type,
        min_score=min_score,
    )
    if not previews:
        typer.echo("没有找到符合条件的待晋升条目")
        raise typer.Exit()

    typer.echo(f"共挑选出 {len(previews)} 条待晋升条目：")
    for preview in previews:
        typer.echo(
            f"[{preview.entry.id}] {preview.entry.title} "
            f"(来源: {preview.source.name}/{preview.source.source_type.value}, "
            f"规则: {preview.rule_match.rule.name}, 得分: {preview.rule_match.score:.2f})"
        )

    if dry_run:
        raise typer.Exit()

    promoted = 0
    for preview in previews:
        try:
            pipeline.promote_entry(preview.entry.id, min_score=min_score)
        except (EntryNotQualifiedError, CandidateAlreadyExistsError):
            continue
        promoted += 1

    typer.echo(f"已生成 {promoted} 条候选需求")


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
    synced: Annotated[
        bool | None,
        typer.Option("--synced/--unsynced", help="按同步状态过滤"),
    ] = None,
    limit: Annotated[int, typer.Option(help="显示的最大条目数", min=1, max=100)] = 20,
) -> None:
    """列出候选需求。"""

    total, items = candidate_needs.list_needs(
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        synced=synced,
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
    except InvalidStatusTransitionError as exc:
        raise typer.BadParameter(str(exc), param_hint="status") from exc

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
    except InvalidStatusTransitionError as exc:
        raise typer.BadParameter(str(exc), param_hint="status") from exc

    typer.echo(f"已将候选需求 #{need.id} 状态更新为 {need.status.value}")


@candidates_app.command("status-logs")
def show_candidate_need_status_logs(
    need_id: Annotated[int, typer.Argument(help="候选需求 ID")]
) -> None:
    """展示候选需求的状态流转记录。"""

    try:
        logs = candidate_needs.list_need_status_logs(need_id)
    except CandidateNeedNotFoundError as exc:
        raise typer.BadParameter("候选需求不存在", param_hint="need_id") from exc

    if not logs:
        typer.echo("暂无状态流转记录")
        raise typer.Exit()

    typer.echo(f"候选需求 #{need_id} 状态流转：")
    for log in logs:
        previous = log.from_status.value if log.from_status else "创建"
        message = (
            f"[{log.id}] {log.changed_at.isoformat()} "
            f"{previous} -> {log.to_status.value}"
        )
        if log.note:
            message += f" - {log.note}"
        typer.echo(message)


@candidates_app.command("sync-logs")
def show_candidate_need_sync_logs(
    need_id: Annotated[int, typer.Argument(help="候选需求 ID")],
    limit: Annotated[int, typer.Option(help="最大返回日志条数", min=1, max=200)] = 20,
    channel: Annotated[
        str | None,
        typer.Option("--channel", help="按通道过滤日志", case_sensitive=False),
    ] = None,
) -> None:
    """展示候选需求的同步审计日志。"""

    try:
        candidate_needs.get_need(need_id)
    except CandidateNeedNotFoundError as exc:
        raise typer.BadParameter("候选需求不存在", param_hint="need_id") from exc

    channel_filter: SyncChannel | None = None
    if channel:
        try:
            channel_filter = SyncChannel(channel)
        except ValueError as exc:
            raise typer.BadParameter("未知的通道", param_hint="channel") from exc

    logs = sync_audit.list_logs(need_id=need_id, channel=channel_filter, limit=limit)
    if not logs:
        typer.echo("暂无同步日志")
        raise typer.Exit()

    channel_label = f"（通道：{channel_filter.value}）" if channel_filter else ""
    typer.echo(f"候选需求 #{need_id} 同步日志{channel_label}：")
    for log in logs:
        meta = ", ".join(f"{key}={value}" for key, value in log.metadata.items()) or "-"
        typer.echo(
            f"[{log.id}] {log.delivered_at.isoformat()} {log.channel.value} "
            f"status={log.status} attempts={log.attempt} meta={meta}"
        )


@candidates_app.command("sync")
def trigger_candidate_need_sync(
    channel: Annotated[
        str,
        typer.Option(
            "--channel",
            help="指定同步通道：webhook/mq/file_drop/all",
            case_sensitive=False,
        ),
    ] = "all",
    limit: Annotated[int, typer.Option("--limit", min=1, max=200, help="单次派发数量")]
    = 20,
    statuses: Annotated[
        list[CandidateNeedStatus] | None,
        typer.Option("--status", help="按状态过滤，可重复", case_sensitive=False),
    ] = None,
    webhook_url: Annotated[
        str | None,
        typer.Option("--webhook-url", help="覆盖配置的 webhook 地址"),
    ] = None,
) -> None:
    """立即向指定通道派发候选需求同步任务。"""

    normalized_statuses = tuple(statuses) if statuses else None
    selected_channels: tuple[SyncChannel, ...] | None
    channel_value = channel.lower()
    if channel_value == "all":
        selected_channels = None
    else:
        try:
            selected_channels = (SyncChannel(channel_value),)
        except ValueError as exc:
            raise typer.BadParameter("未知的通道", param_hint="channel") from exc

    queued = task_queue.enqueue_sync_tasks(
        webhook_url=webhook_url,
        statuses=normalized_statuses,
        batch_size=limit,
        channels=selected_channels,
    )
    if queued == 0:
        typer.echo("没有可派发的候选需求，或通道尚未启用")
        raise typer.Exit(code=1)

    channel_label = (
        "所有已启用通道"
        if selected_channels is None
        else ",".join(ch.value for ch in selected_channels)
    )
    typer.echo(f"已派发 {queued} 条候选需求到 {channel_label}")


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
    synced: Annotated[
        bool | None,
        typer.Option("--synced/--unsynced", help="按同步状态过滤"),
    ] = None,
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
        synced=synced,
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


@candidates_app.command("schedule-export")
def schedule_candidate_need_export(
    format: Annotated[
        str,
        typer.Option("--format", help="导出格式", case_sensitive=False),
    ] = "json",
    statuses: Annotated[
        list[CandidateNeedStatus] | None,
        typer.Option("--status", help="按状态过滤，可重复", case_sensitive=False),
    ] = None,
    search: Annotated[str | None, typer.Option(help="关键字搜索") ] = None,
    raw_entry_id: Annotated[int | None, typer.Option(help="原始条目 ID 过滤")] = None,
    synced: Annotated[
        bool | None,
        typer.Option("--synced/--unsynced", help="按同步状态过滤"),
    ] = None,
    limit: Annotated[int | None, typer.Option(help="最大导出数量", min=1, max=5000)] = None,
) -> None:
    """创建异步导出任务并交由队列执行。"""

    fmt = format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("format 必须为 json 或 csv", param_hint="format")
    job = export_jobs.create_candidate_export_job(
        format=fmt,
        statuses=statuses,
        search=search,
        raw_entry_id=raw_entry_id,
        synced=synced,
        limit=limit,
    )
    task_queue.enqueue_export_job(job.id)
    typer.echo(
        f"已创建导出任务 #{job.id}，格式 {job.format}，状态 {job.status.value}"
    )


@candidates_app.command("export-status")
def show_candidate_export_status(
    job_id: Annotated[int, typer.Argument(help="导出任务 ID")]
) -> None:
    """查看异步导出任务的执行状态。"""

    try:
        job = export_jobs.get_export_job(job_id)
    except ExportJobNotFoundError as exc:
        raise typer.BadParameter("导出任务不存在", param_hint="job_id") from exc

    typer.echo(
        f"任务 #{job.id}: status={job.status.value}, records={job.record_count}, "
        f"file={job.file_path or '-'}"
    )


if __name__ == "__main__":
    app()
