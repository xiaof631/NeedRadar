"""pydantic 接口的极简兼容实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Type, TypeVar, get_args, get_origin


@dataclass
class FieldInfo:
    default: Any
    metadata: dict[str, Any]


def Field(default: Any = Ellipsis, **metadata: Any) -> FieldInfo:
    """创建字段描述信息。"""

    return FieldInfo(default=default, metadata=metadata)


def ConfigDict(**config: Any) -> dict[str, Any]:
    """模拟 pydantic 的 ConfigDict。"""

    return dict(config)


AnyHttpUrl = str
PositiveInt = int


class ModelMeta(type):
    """收集字段定义的元类。"""

    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        annotations: dict[str, Any] = {}
        field_info: dict[str, FieldInfo] = {}
        for base in bases:
            annotations.update(getattr(base, "__annotations__", {}))
            field_info.update(getattr(base, "_field_info", {}))

        annotations.update(namespace.get("__annotations__", {}))
        for key, value in list(annotations.items()):
            if get_origin(value) is ClassVar:
                annotations.pop(key)
                field_info.pop(key, None)
        for field_name, annotation in namespace.get("__annotations__", {}).items():
            if get_origin(annotation) is ClassVar:
                continue
            if field_name in namespace:
                default = namespace[field_name]
                if isinstance(default, FieldInfo):
                    field_info[field_name] = default
                else:
                    field_info[field_name] = FieldInfo(default=default, metadata={})
                del namespace[field_name]
            else:
                field_info.setdefault(field_name, FieldInfo(default=Ellipsis, metadata={}))

        namespace["__annotations__"] = annotations
        namespace["_field_info"] = field_info
        return super().__new__(mcls, name, bases, namespace)


ModelT = TypeVar("ModelT", bound="BaseModel")


class BaseModel(metaclass=ModelMeta):
    """简化版本的 BaseModel。"""

    model_config: ClassVar[dict[str, Any]] = {}

    def __init__(self, **data: Any) -> None:
        values: dict[str, Any] = {}
        set_fields: set[str] = set()
        for name, info in self._field_info.items():
            if name in data:
                values[name] = data[name]
                set_fields.add(name)
            elif info.default is not Ellipsis:
                values[name] = info.default
            else:
                raise ValueError(f"Missing field '{name}'")
        self.__dict__.update(values)
        self.__dict__["_set_fields"] = set_fields

    def model_dump(self, *, exclude_unset: bool = False, **_: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        set_fields = self.__dict__.get("_set_fields", set())
        for name in self._field_info:
            if exclude_unset and name not in set_fields:
                continue
            result[name] = self._export_value(getattr(self, name))
        return result

    @classmethod
    def model_validate(cls: Type[ModelT], data: Any) -> ModelT:
        if isinstance(data, cls):
            return data
        if isinstance(data, dict):
            return cls(**data)
        config = getattr(cls, "model_config", {})
        if config.get("from_attributes") and data is not None:
            values = {name: getattr(data, name) for name in cls._field_info if hasattr(data, name)}
            return cls(**values)
        raise TypeError(f"Unsupported data for {cls.__name__}")

    @classmethod
    def _export_value(cls, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump()
        if isinstance(value, list):
            return [cls._export_value(item) for item in value]
        if isinstance(value, tuple):
            return [cls._export_value(item) for item in value]
        return value

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={getattr(self, name)!r}" for name in self._field_info)
        return f"{self.__class__.__name__}({fields})"


BaseModel._field_info.pop("model_config", None)

__all__ = [
    "AnyHttpUrl",
    "BaseModel",
    "ConfigDict",
    "Field",
    "FieldInfo",
    "PositiveInt",
]
