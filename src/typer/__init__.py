"""Tiny subset of Typer required for the exercises."""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Union, get_args, get_origin


class BadParameter(Exception):
    """Exception raised when option parsing fails."""


class _Colors:
    YELLOW = "yellow"


colors = _Colors()


@dataclass
class OptionInfo:
    default: Any
    min: Optional[int] = None
    help: Optional[str] = None
    is_flag: bool = False

    @property
    def required(self) -> bool:
        return self.default is ...


def Option(
    default: Any = ...,
    *,
    min: Optional[int] = None,
    help: Optional[str] = None,
    is_flag: bool = False,
) -> OptionInfo:
    return OptionInfo(default=default, min=min, help=help, is_flag=is_flag)


def echo(message: str) -> None:
    print(message)


def secho(message: str, *, fg: Optional[str] = None) -> None:  # pragma: no cover - colour ignored
    print(message)


class Typer:
    """Command container mimicking Typer's API surface used in tests."""

    def __init__(self, *, help: Optional[str] = None) -> None:
        self.help = help or ""
        self._commands: Dict[str, Callable[..., Any]] = {}
        self._options: Dict[str, Dict[str, OptionInfo]] = {}
        self._callback: Optional[Callable[[], Any]] = None

    def command(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._commands[func.__name__] = func
            self._options[func.__name__] = self._extract_options(func)
            return func

        return decorator

    def callback(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._callback = func
            return func

        return decorator

    def _extract_options(self, func: Callable[..., Any]) -> Dict[str, OptionInfo]:
        signature = inspect.signature(func)
        options: Dict[str, OptionInfo] = {}
        for name, parameter in signature.parameters.items():
            default = parameter.default
            if isinstance(default, OptionInfo):
                options[name] = default
            else:
                options[name] = OptionInfo(default=default)
        return options

    def _convert_value(self, value: str, annotation: Any) -> Any:
        origin = get_origin(annotation)
        if origin is Union:
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(args) == 1:
                annotation = args[0]
            else:
                annotation = str
        if annotation in (int, float, str):
            return annotation(value)
        if annotation is bool:
            return value.lower() in {"1", "true", "yes"}
        return value

    def _parse(self, command: str, args: Iterable[str]) -> Dict[str, Any]:
        options = self._options[command]
        signature = inspect.signature(self._commands[command])
        values: Dict[str, Any] = {}
        tokens: List[str] = list(args)
        index = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if not token.startswith("--"):
                raise BadParameter(f"unexpected argument '{token}'")
            name = token[2:].replace("-", "_")
            if name not in options:
                raise BadParameter(f"unknown option '{token}'")
            annotation = signature.parameters[name].annotation
            option_info = options[name]
            next_is_option = index >= len(tokens) or tokens[index].startswith("--")
            if (annotation is bool or option_info.is_flag) and next_is_option:
                values[name] = True
                continue
            if index >= len(tokens):
                raise BadParameter(f"option '{token}' expects a value")
            raw_value = tokens[index]
            index += 1
            converted = self._convert_value(raw_value, annotation)
            if option_info.min is not None and isinstance(converted, (int, float)):
                if converted < option_info.min:
                    raise BadParameter(f"option '{token}' must be >= {option_info.min}")
            values[name] = converted
        for name, option in options.items():
            if name not in values:
                if option.required:
                    raise BadParameter(f"missing required option '--{name.replace('_', '-')}'")
                values[name] = option.default if option.default is not ... else None
        return values

    def _run(self, argv: Iterable[str]) -> None:
        args = list(argv)
        if self._callback:
            self._callback()
        if not args:
            raise SystemExit(0)
        command_name, *command_args = args
        if command_name not in self._commands:
            raise SystemExit(1)
        parsed = self._parse(command_name, command_args)
        self._commands[command_name](**parsed)

    def __call__(self) -> None:  # pragma: no cover - mirrors Typer
        self._run(sys.argv[1:])


__all__ = ["Typer", "Option", "BadParameter", "colors", "echo", "secho"]
