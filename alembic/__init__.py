"""提供最小化的 Alembic context。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class _Context:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            config_file_name=None,
            config_ini_section="alembic",
            main_options={},
        )
        self._offline = True

    def get_main_option(self, key: str) -> str:
        return self.config.main_options.get(key, "")

    def set_main_option(self, key: str, value: str) -> None:
        self.config.main_options[key] = value

    def get_section(self, section: str, default: dict[str, Any]) -> dict[str, Any]:
        return {**default, **{f"{section}url": self.get_main_option("sqlalchemy.url")}}

    def configure(self, **_: Any) -> None:  # noqa: D401
        return None

    def begin_transaction(self):  # noqa: D401
        class _Transaction:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):  # type: ignore[override]
                return None

        return _Transaction()

    def run_migrations(self) -> None:
        return None

    def is_offline_mode(self) -> bool:
        return self._offline


context = _Context()

__all__ = ["context"]
