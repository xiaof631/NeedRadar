"""NeedRadar 命令行入口。"""

import asyncio
from typing import Annotated

import typer
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

app = typer.Typer(help="NeedRadar 工具集")
logger = get_logger(__name__)


@app.command()
def show_config() -> None:
    """打印当前配置。"""

    settings = get_settings()
    configure_logging()
    logger.info("current-settings", **settings.model_dump())


@app.command()
def init_db(
    echo: Annotated[
        bool,
        typer.Option(help="是否输出 SQL 语句", rich_help_panel="数据库"),
    ] = False,
) -> None:
    """初始化数据库连接（仅测试连接有效性）。"""

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

    settings = get_settings()
    configure_logging()
    engine: AsyncEngine = create_async_engine(settings.database_url, echo=echo)

    async def _ping() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    asyncio.run(_ping())
    logger.info("database-initialized", database_url=settings.database_url)


if __name__ == "__main__":
    app()
