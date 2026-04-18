"""Typer 的轻量兼容层，支持当前仓库所需的命令解析。"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

_MISSING = object()


@dataclass
class ArgumentInfo:
    default: Any = _MISSING
    help: str | None = None
    metavar: str | None = None
    case_sensitive: bool = True
    min: float | int | None = None
    max: float | int | None = None


@dataclass
class OptionInfo:
    param_decls: tuple[str, ...] = ()
    default: Any = None
    help: str | None = None
    rich_help_panel: str | None = None
    case_sensitive: bool = True
    min: float | int | None = None
    max: float | int | None = None
    metavar: str | None = None


class BadParameter(ValueError):
    def __init__(self, message: str, param_hint: str | None = None) -> None:
        super().__init__(message)
        self.param_hint = param_hint


class Exit(Exception):
    def __init__(self, code: int = 0) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class _ParameterSpec:
    name: str
    annotation: Any
    default: Any
    metadata: ArgumentInfo | OptionInfo | None

    @property
    def is_option(self) -> bool:
        return isinstance(self.metadata, OptionInfo)

    @property
    def is_argument(self) -> bool:
        return not self.is_option

    @property
    def option_names(self) -> tuple[str, ...]:
        if not isinstance(self.metadata, OptionInfo):
            return ()
        if self.metadata.param_decls:
            names: list[str] = []
            for decl in self.metadata.param_decls:
                if "/" in decl:
                    names.extend(part for part in decl.split("/") if part)
                else:
                    names.append(decl)
            return tuple(names)
        return (f"--{self.name.replace('_', '-')}",)

    @property
    def expects_multiple(self) -> bool:
        origin = get_origin(_strip_optional(self.annotation))
        return origin is list

    @property
    def is_bool_flag(self) -> bool:
        return _strip_optional(self.annotation) is bool

    @property
    def case_sensitive(self) -> bool:
        metadata = self.metadata
        if isinstance(metadata, (ArgumentInfo, OptionInfo)):
            return metadata.case_sensitive
        return True

    @property
    def min(self) -> float | int | None:
        metadata = self.metadata
        if isinstance(metadata, (ArgumentInfo, OptionInfo)):
            return metadata.min
        return None

    @property
    def max(self) -> float | int | None:
        metadata = self.metadata
        if isinstance(metadata, (ArgumentInfo, OptionInfo)):
            return metadata.max
        return None


class Typer:
    """轻量命令行调度器。"""

    def __init__(self, help: str | None = None) -> None:
        self.help = help
        self.commands: dict[str, Callable[..., Any]] = {}
        self.sub_apps: dict[str, "Typer"] = {}

    def command(
        self, name: str | None = None, **_: Any
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            command_name = name or func.__name__.replace("_", "-")
            self.commands[command_name] = func
            if command_name != func.__name__:
                self.commands[func.__name__] = func
            return func

        return decorator

    def add_typer(self, app: "Typer", name: str) -> None:
        self.sub_apps[name] = app

    def __call__(self) -> None:
        try:
            self._invoke(list(sys.argv[1:]))
        except Exit as exc:
            raise SystemExit(exc.code) from None
        except BadParameter as exc:
            message = str(exc)
            if exc.param_hint:
                message = f"{message} ({exc.param_hint})"
            print(message, file=sys.stderr)
            raise SystemExit(2) from None

    def _invoke(self, argv: list[str]) -> Any:
        if argv and argv[0] in self.sub_apps:
            return self.sub_apps[argv[0]]._invoke(argv[1:])
        if not argv:
            return None
        command_name = argv[0]
        command = self.commands.get(command_name)
        if command is None:
            raise BadParameter(f"未知命令: {command_name}")
        kwargs = _parse_command_arguments(command, argv[1:])
        return command(**kwargs)


def Argument(
    default: Any = _MISSING,
    *,
    help: str | None = None,
    metavar: str | None = None,
    case_sensitive: bool = True,
    min: float | int | None = None,
    max: float | int | None = None,
) -> ArgumentInfo:
    return ArgumentInfo(
        default=default,
        help=help,
        metavar=metavar,
        case_sensitive=case_sensitive,
        min=min,
        max=max,
    )


def Option(
    *param_decls: str,
    help: str | None = None,
    rich_help_panel: str | None = None,
    case_sensitive: bool = True,
    min: float | int | None = None,
    max: float | int | None = None,
    metavar: str | None = None,
) -> OptionInfo:
    return OptionInfo(
        param_decls=tuple(param_decls),
        default=None,
        help=help,
        rich_help_panel=rich_help_panel,
        case_sensitive=case_sensitive,
        min=min,
        max=max,
        metavar=metavar,
    )


def echo(message: Any = "") -> None:
    print(message)


def _parse_command_arguments(command: Callable[..., Any], argv: list[str]) -> dict[str, Any]:
    signature = inspect.signature(command)
    hints = get_type_hints(command, include_extras=True)
    specs = [_build_parameter_spec(parameter, hints.get(parameter.name, parameter.annotation)) for parameter in signature.parameters.values()]
    option_specs = [spec for spec in specs if spec.is_option]
    argument_specs = [spec for spec in specs if spec.is_argument]

    option_index: dict[str, _ParameterSpec] = {}
    for spec in option_specs:
        for name in spec.option_names:
            option_index[name] = spec

    parsed_options: dict[str, Any] = {}
    positional_tokens: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token.startswith("--"):
            spec = option_index.get(token)
            if spec is None:
                raise BadParameter(f"未知选项: {token}")
            if spec.is_bool_flag:
                value = True
                names = spec.option_names
                if len(names) == 2 and token == names[1]:
                    value = False
                parsed_options[spec.name] = value
                index += 1
                continue
            if index + 1 >= len(argv):
                raise BadParameter(f"选项缺少值: {token}", param_hint=spec.name)
            raw_value = argv[index + 1]
            parsed_options.setdefault(spec.name, [])
            parsed_options[spec.name].append(raw_value)
            index += 2
            continue
        positional_tokens.append(token)
        index += 1

    resolved: dict[str, Any] = {}
    position = 0
    for spec in argument_specs:
        if spec.expects_multiple:
            values = positional_tokens[position:]
            if not values and spec.default is _MISSING:
                raise BadParameter("缺少参数", param_hint=spec.name)
            resolved[spec.name] = [
                _coerce_value(value, spec.annotation, case_sensitive=spec.case_sensitive, minimum=spec.min, maximum=spec.max)
                for value in values
            ]
            position = len(positional_tokens)
            continue
        if position >= len(positional_tokens):
            if spec.default is not _MISSING:
                resolved[spec.name] = spec.default
                continue
            raise BadParameter("缺少参数", param_hint=spec.name)
        resolved[spec.name] = _coerce_value(
            positional_tokens[position],
            spec.annotation,
            case_sensitive=spec.case_sensitive,
            minimum=spec.min,
            maximum=spec.max,
        )
        position += 1

    if position < len(positional_tokens):
        raise BadParameter(f"多余参数: {' '.join(positional_tokens[position:])}")

    for spec in option_specs:
        if spec.name not in parsed_options:
            if spec.expects_multiple:
                resolved[spec.name] = [] if spec.default in (_MISSING, None) else spec.default
            elif spec.default is not _MISSING:
                resolved[spec.name] = spec.default
            else:
                resolved[spec.name] = None
            continue
        raw_value = parsed_options[spec.name]
        if spec.is_bool_flag:
            resolved[spec.name] = raw_value
            continue
        if spec.expects_multiple:
            resolved[spec.name] = [
                _coerce_value(value, spec.annotation, case_sensitive=spec.case_sensitive, minimum=spec.min, maximum=spec.max)
                for value in raw_value
            ]
            continue
        resolved[spec.name] = _coerce_value(
            raw_value[-1],
            spec.annotation,
            case_sensitive=spec.case_sensitive,
            minimum=spec.min,
            maximum=spec.max,
        )

    return resolved


def _build_parameter_spec(parameter: inspect.Parameter, annotation: Any) -> _ParameterSpec:
    base_annotation, metadata = _unwrap_annotated(annotation)
    default = parameter.default
    if default is inspect._empty:
        if isinstance(metadata, ArgumentInfo) and metadata.default is not _MISSING:
            default = metadata.default
        else:
            default = _MISSING
    return _ParameterSpec(
        name=parameter.name,
        annotation=base_annotation,
        default=default,
        metadata=metadata,
    )


def _unwrap_annotated(annotation: Any) -> tuple[Any, ArgumentInfo | OptionInfo | None]:
    if get_origin(annotation) is not None and str(get_origin(annotation)).endswith("Annotated"):
        args = get_args(annotation)
        base = args[0]
        metadata = next((item for item in args[1:] if isinstance(item, (ArgumentInfo, OptionInfo))), None)
        return base, metadata
    return annotation, None


def _strip_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    args = [item for item in get_args(annotation) if item is not type(None)]
    if len(args) == 1:
        return args[0]
    return annotation


def _coerce_value(
    raw_value: str,
    annotation: Any,
    *,
    case_sensitive: bool,
    minimum: float | int | None,
    maximum: float | int | None,
) -> Any:
    target = _strip_optional(annotation)
    origin = get_origin(target)
    if origin is list:
        inner = get_args(target)[0]
        return [_coerce_value(raw_value, inner, case_sensitive=case_sensitive, minimum=minimum, maximum=maximum)]

    if target in (Any, inspect._empty, str):
        return raw_value
    if target is int:
        value = int(raw_value)
    elif target is float:
        value = float(raw_value)
    elif target is bool:
        lowered = raw_value.lower()
        if lowered in {"1", "true", "yes", "on"}:
            value = True
        elif lowered in {"0", "false", "no", "off"}:
            value = False
        else:
            raise BadParameter(f"无法解析布尔值: {raw_value}")
    elif target is Path:
        value = Path(raw_value)
    elif target is datetime:
        value = datetime.fromisoformat(raw_value)
    elif inspect.isclass(target) and issubclass(target, Enum):
        value = _coerce_enum(raw_value, target, case_sensitive=case_sensitive)
    else:
        value = target(raw_value)

    if minimum is not None and value < minimum:
        raise BadParameter(f"值不能小于 {minimum}")
    if maximum is not None and value > maximum:
        raise BadParameter(f"值不能大于 {maximum}")
    return value


def _coerce_enum(raw_value: str, enum_type: type[Enum], *, case_sensitive: bool) -> Enum:
    normalized = raw_value if case_sensitive else raw_value.lower()
    for member in enum_type:
        candidate_values = [str(member.value), member.name]
        if not case_sensitive:
            candidate_values = [item.lower() for item in candidate_values]
        if normalized in candidate_values:
            return member
    raise BadParameter(f"非法枚举值: {raw_value}")


__all__ = [
    "Argument",
    "ArgumentInfo",
    "BadParameter",
    "echo",
    "Exit",
    "Option",
    "OptionInfo",
    "Typer",
]
