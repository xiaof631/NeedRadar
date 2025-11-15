"""Typer 的极简实现，满足基本命令注册需求。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class OptionInfo:
    default: Any
    help: str | None = None
    rich_help_panel: str | None = None


class Typer:
    """极简命令行调度器。"""

    def __init__(self, help: str | None = None) -> None:
        self.help = help
        self.commands: dict[str, Callable[..., Any]] = {}

    def command(
        self, name: str | None = None, **_: Any
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.commands[name or func.__name__] = func
            return func

        return decorator

    def __call__(self) -> None:
        # 离线环境不解析命令参数，直接返回
        return None


def Option(*, help: str | None = None, rich_help_panel: str | None = None) -> OptionInfo:
    return OptionInfo(default=None, help=help, rich_help_panel=rich_help_panel)


__all__ = ["Typer", "Option"]
