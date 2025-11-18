"""应用配置模块。"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from typing import Any, Literal

from app.models import CandidateNeedStatus
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
    downstream_mq_enabled: bool = Field(
        default=False,
        description="是否启用消息队列推送候选需求",
    )
    downstream_mq_broker_url: str | None = Field(
        default=None,
        description="消息队列 Broker 连接串（如 amqp:// 或 redis://）",
    )
    downstream_mq_exchange: str = Field(
        default="needradar.candidate_needs",
        description="候选需求推送使用的 MQ Exchange",
    )
    downstream_mq_routing_key: str = Field(
        default="needradar.candidate_needs",
        description="候选需求推送使用的 Routing Key",
    )
    downstream_filesystem_enabled: bool = Field(
        default=False,
        description="是否启用基于文件系统的 file drop 同步通道",
    )
    downstream_filesystem_dir: str = Field(
        default="./data/file_drop",
        description="file drop 通道写入的目录",
    )
    downstream_filesystem_format: Literal["json", "jsonl"] = Field(
        default="json",
        description="file drop 输出格式，支持 json 或 jsonl",
    )
    export_output_dir: str = Field(
        default="./data/exports",
        description="导出结果写入的目录",
    )

    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="Celery 使用的消息队列（Redis/RabbitMQ）连接字符串",
    )
    celery_result_backend: str | None = Field(
        default="redis://localhost:6379/1",
        description="Celery 任务结果存储地址，可为空",
    )
    celery_task_default_queue: str = Field(
        default="needradar",
        description="Celery 默认任务队列名称",
    )
    celery_task_always_eager: bool = Field(
        default=False,
        description="测试环境下是否同步执行任务",
    )
    celery_worker_max_tasks_per_child: int | None = Field(
        default=200,
        description="每个 worker 进程处理的最大任务数，避免内存泄漏",
    )
    celery_task_soft_time_limit: int = Field(
        default=60,
        description="任务软超时时间（秒）",
        ge=1,
    )
    celery_task_time_limit: int = Field(
        default=90,
        description="任务硬超时时间（秒）",
        ge=1,
    )
    celery_downstream_request_timeout: float = Field(
        default=10.0,
        description="推送下游 Webhook 时 HTTP 请求的超时时间（秒）",
        gt=0,
    )

    api_tokens: tuple[str, ...] = Field(
        default=(),
        description="可访问 API 的 Token 列表，默认关闭认证",
    )

    telemetry_enabled: bool = Field(
        default=False,
        description="是否启用 OpenTelemetry 链路追踪",
    )
    telemetry_service_name: str = Field(
        default="needradar-api",
        description="OpenTelemetry 服务名称",
    )
    telemetry_otlp_endpoint: str | None = Field(
        default=None,
        description="OTLP 导出目标，未配置时默认输出至控制台",
    )
    telemetry_otlp_insecure: bool = Field(
        default=True,
        description="向 OTLP endpoint 传输时是否允许非 TLS 连接",
    )
    telemetry_sample_ratio: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="链路采样率，0-1 之间",
    )
    telemetry_excluded_urls: tuple[str, ...] = Field(
        default=("/metrics", "/health"),
        description="无需采样的 URL 前缀",
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

    instance = Settings(**overrides)
    instance.api_tokens = _normalize_api_tokens(instance.api_tokens)
    return instance


def _normalize_api_tokens(value: Any) -> tuple[str, ...]:
    """将配置值转换为标准的 Token 元组。"""

    if value is None:
        return ()
    if isinstance(value, str):
        tokens = [token.strip() for token in value.split(",") if token.strip()]
        return tuple(tokens)
    if isinstance(value, Iterable):
        return tuple(item for item in value if isinstance(item, str) and item)
    return ()


settings = get_settings()
