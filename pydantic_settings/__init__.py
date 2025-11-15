"""pydantic-settings 的极简替代实现。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import FieldInfo


@dataclass
class SettingsConfigDict:
    env_file: tuple[str, ...] = ()
    env_prefix: str = ""


class BaseSettings:
    """读取环境变量并合并默认值。"""

    model_config = SettingsConfigDict()

    def __init__(self, **overrides: Any) -> None:
        env_data = self._load_env_files()
        env_prefix = self.model_config.env_prefix
        values: dict[str, Any] = {}
        annotations = getattr(self.__class__, "__annotations__", {})

        for field in annotations:
            attr_value = getattr(self.__class__, field, None)
            default = attr_value.default if isinstance(attr_value, FieldInfo) else attr_value
            env_key = f"{env_prefix}{field}".upper()
            if env_key in env_data:
                values[field] = self._coerce_type(annotations[field], env_data[env_key])
            else:
                values[field] = default

        values.update(overrides)

        for key, value in values.items():
            setattr(self, key, value)

    def _load_env_files(self) -> dict[str, str]:
        data: dict[str, str] = {k: v for k, v in os.environ.items()}
        for file in self.model_config.env_file:
            path = Path(file)
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line or line.strip().startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.strip().split("=", 1)
                    data[key] = value
        return data

    def _coerce_type(self, typ: Any, value: str) -> Any:
        origin = getattr(typ, "__origin__", None)
        if origin is bool or typ is bool:
            return value.lower() in {"1", "true", "yes", "on"}
        if origin is int or typ is int:
            return int(value)
        if origin is float or typ is float:
            return float(value)
        return value

    def model_dump(self) -> dict[str, Any]:
        annotations = getattr(self.__class__, "__annotations__", {})
        return {field: getattr(self, field) for field in annotations}


__all__ = ["BaseSettings", "SettingsConfigDict"]
