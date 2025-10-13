"""Testing helpers compatible with the simplified Typer implementation."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass
from typing import Any, Iterable

from . import BadParameter, Typer


@dataclass
class Result:
    exit_code: int
    stdout: str


class CliRunner:
    """Execute Typer applications while capturing stdout."""

    def invoke(self, app: Typer, args: Iterable[str]) -> Result:
        buffer = io.StringIO()
        exit_code = 0
        try:
            with contextlib.redirect_stdout(buffer):
                app._run(args)
        except SystemExit as exc:
            exit_code = int(exc.code) if isinstance(exc.code, int) else 1
        except BadParameter as exc:
            exit_code = 2
            buffer.write(str(exc))
        except Exception as exc:  # pragma: no cover - safety net for debugging
            exit_code = 1
            buffer.write(str(exc))
        return Result(exit_code=exit_code, stdout=buffer.getvalue())
