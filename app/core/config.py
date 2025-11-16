"""应用配置模块。"""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models import CandidateNeedStatus


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
    llm_provider: str = Field(
        default="heuristic",
        description="LLM 客户端提供者标识，默认为启发式实现",
    )
    llm_timeout: float = Field(
        default=8.0,
        description="LLM 分析超时时间（秒），用于调度层配置",
        ge=0.1,
    )
    scheduler_fetch_interval_seconds: int = Field(
        default=900,
        description="调度器触发 RSS 抓取任务的间隔（秒）",
        ge=60,
    )
    scheduler_promote_interval_seconds: int = Field(
        default=600,
        description="调度器触发候选需求晋升任务的间隔（秒）",
        ge=60,
    )
    scheduler_promotion_batch_size: int = Field(
        default=20,
        description="每次调度处理的原始条目数量上限",
        ge=1,
        le=500,
    )
    scheduler_min_rule_score: float | None = Field(
        default=None,
        description="调度器触发晋升时应用的最低规则得分阈值",
        ge=0.0,
        le=1.0,
    )
    scheduler_downstream_interval_seconds: int = Field(
        default=1800,
        description="调度器触发下游同步的间隔（秒）",
        ge=60,
    )
    downstream_webhook_url: str | None = Field(
        default=None,
        description="候选需求同步的 Webhook 地址，为空则不执行",
    )
    downstream_sync_statuses: tuple[CandidateNeedStatus, ...] = Field(
        default=(
            CandidateNeedStatus.APPROVED,
            CandidateNeedStatus.IN_DISCOVERY,
        ),
        description="需要推送至下游的候选需求状态",
    )
    downstream_sync_batch_size: int = Field(
        default=20,
        description="单次下游同步的最大候选需求数量",
        ge=1,
        le=200,
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
