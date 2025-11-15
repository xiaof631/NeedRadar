"""structlog 的轻量包装，记录到标准 logging。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

_logger_cache: dict[str, BoundLogger] = {}


@dataclass
class BoundLogger:
    name: str
    _context: dict[str, Any]

    def bind(self, **kwargs: Any) -> BoundLogger:
        new_context = {**self._context, **kwargs}
        return BoundLogger(self.name, new_context)

    def info(self, event: str, **kwargs: Any) -> None:
        logging.getLogger(self.name).info("%s %s", event, {**self._context, **kwargs})


def get_logger(name: str) -> BoundLogger:
    if name not in _logger_cache:
        _logger_cache[name] = BoundLogger(name=name, _context={})
    return _logger_cache[name]


class stdlib:
    BoundLogger = BoundLogger

    @staticmethod
    def add_log_level(
        logger: BoundLogger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        return event_dict

    @staticmethod
    def add_logger_name(
        logger: BoundLogger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        event_dict.setdefault("logger", logger.name)
        return event_dict

    @staticmethod
    def filter_by_level(
        logger: BoundLogger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        return event_dict


class processors:
    @staticmethod
    def TimeStamper(fmt: str = "iso") -> Any:  # noqa: D401
        def timestamper(
            logger: BoundLogger, method_name: str, event_dict: dict[str, Any]
        ) -> dict[str, Any]:
            event_dict.setdefault("timestamp", "")
            return event_dict

        return timestamper

    @staticmethod
    def format_exc_info(
        logger: BoundLogger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        return event_dict

    class JSONRenderer:
        def __call__(
            self, logger: BoundLogger, method_name: str, event_dict: dict[str, Any]
        ) -> dict[str, Any]:
            return event_dict


def configure(
    processors: list[Any],
    wrapper_class: Any,
    cache_logger_on_first_use: bool = True,
) -> None:
    logging.basicConfig(level=logging.INFO)


def make_filtering_bound_logger(level: int) -> type[BoundLogger]:
    return BoundLogger
