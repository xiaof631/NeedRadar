"""应用配置模块。"""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用的核心配置。"""

    debug: bool = Field(default=False, description="是否启用调试模式")
    app_name: str = Field(default="NeedRadar API", description="FastAPI 应用名称")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/needradar.db",
        description="SQLAlchemy 数据库连接字符串",
    )
    alembic_database_url: str | None = Field(
        default=None,
        description="Alembic 迁移所使用的同步数据库 URL，可覆盖 database_url",
    )

    model_config = SettingsConfigDict(env_file=('.env', '.env.local'), env_prefix="NEEDRADAR_")

    @property
    def sync_database_url(self) -> str:
        """返回 Alembic 迁移使用的同步数据库连接 URL。"""

        if self.alembic_database_url:
            return self.alembic_database_url
        if self.database_url.startswith("sqlite+aiosqlite"):
            return self.database_url.replace("sqlite+aiosqlite", "sqlite")
        return self.database_url


@lru_cache
def get_settings(**overrides: Any) -> Settings:
    """获取应用配置，支持覆写默认值。"""

    return Settings(**overrides)


settings = get_settings()
