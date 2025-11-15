"""NeedRadar 命令行入口。"""

from typing import Annotated

import typer

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models import SourceStatus
from app.services import rss_sources

app = typer.Typer(help="NeedRadar 工具集")
logger = get_logger(__name__)

rss_app = typer.Typer(help="RSS 源管理")
app.add_typer(rss_app, name="rss")


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
        typer.echo(
            f"[{source.id}] {source.name} - {source.url} (分类: {source.category or '-'}, 状态: {source.status})"
        )


@rss_app.command("create")
def create_source(
    name: Annotated[str, typer.Argument(help="RSS 源名称")],
    url: Annotated[str, typer.Argument(help="RSS 地址")],
    frequency: Annotated[int, typer.Option(help="抓取频率（秒）", min=60)] = 3600,
    category: Annotated[str | None, typer.Option(help="分类标签")]=None,
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
    name: Annotated[str | None, typer.Option(help="名称")]=None,
    url: Annotated[str | None, typer.Option(help="RSS 地址")]=None,
    frequency: Annotated[int | None, typer.Option(help="抓取频率（秒）", min=60)]=None,
    category: Annotated[str | None, typer.Option(help="分类标签")]=None,
    status: Annotated[SourceStatus | None, typer.Option(help="状态", case_sensitive=False)]=None,
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


if __name__ == "__main__":
    app()
