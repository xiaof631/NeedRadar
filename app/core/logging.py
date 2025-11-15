"""结构化日志配置。"""

import logging
from typing import Any

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    """初始化 structlog 与标准库日志。"""

    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level)


def get_logger(name: str, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """获取绑定初始上下文的 logger。"""

    return structlog.get_logger(name).bind(**initial_values)
