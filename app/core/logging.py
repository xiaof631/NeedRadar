"""结构化日志配置。"""

import logging
from typing import Any

import structlog

_SENSITIVE_KEYS = ("token", "secret", "password", "key", "authorization")


def configure_logging(level: int = logging.INFO) -> None:
    """初始化 structlog 与标准库日志。"""

    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _mask_sensitive_values,
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


def get_logger(name: str, **initial_values: Any) -> Any:
    """获取绑定初始上下文的 logger。"""

    return structlog.get_logger(name).bind(**initial_values)


def _mask_sensitive_values(
    _: Any,
    __: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """对日志中的敏感字段进行脱敏。"""

    for key in tuple(event_dict.keys()):
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_KEYS):
            event_dict[key] = "***redacted***"
    return event_dict
