from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from types import TracebackType
from typing import TextIO

from tqdm import tqdm


SUPPORTED_PROGRESS_FORMATS = {"auto", "text", "json", "off"}


def _json_default(value: object) -> str:
    return str(value)


@dataclass
class ProgressTask:
    reporter: "ProgressReporter"
    label: str
    total: int | None = None

    def __post_init__(self) -> None:
        self.count = 0
        self._bar = None
        if self.reporter.mode == "tqdm":
            self._bar = tqdm(
                total=self.total,
                desc=self.label,
                unit="item",
                file=self.reporter.stream,
                leave=False,
            )
        elif self.reporter.mode == "text":
            self.reporter.emit("start", self.label, total=self.total)
        elif self.reporter.mode == "json":
            self.reporter.emit("start", self.label, total=self.total)

    def update(self, advance: int = 1, **fields: object) -> None:
        if not self.reporter.enabled:
            return
        self.count += advance
        if self._bar is not None:
            detail = fields.get("detail")
            if detail is not None:
                self._bar.set_postfix_str(str(detail), refresh=False)
            self._bar.update(advance)
        elif self.reporter.mode == "json":
            self.reporter.emit("progress", self.label, current=self.count, total=self.total, **fields)

    def close(self) -> None:
        if self._bar is not None:
            self._bar.close()
        elif self.reporter.mode in {"text", "json"}:
            self.reporter.emit("done", self.label, current=self.count, total=self.total)

    def __enter__(self) -> "ProgressTask":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class ProgressReporter:
    def __init__(
        self,
        *,
        progress_format: str = "auto",
        quiet: bool = False,
        stream: TextIO | None = None,
    ) -> None:
        if progress_format not in SUPPORTED_PROGRESS_FORMATS:
            raise ValueError(f"Unsupported progress format: {progress_format!r}")
        self.stream = stream if stream is not None else sys.stderr
        self.enabled = not quiet and progress_format != "off"
        if not self.enabled:
            self.mode = "off"
        elif progress_format == "auto":
            self.mode = "tqdm" if self.stream.isatty() else "text"
        else:
            self.mode = progress_format

    def emit(self, event: str, message: str, **fields: object) -> None:
        if not self.enabled:
            return
        if self.mode == "json":
            payload = {"event": event, "message": message, **fields}
            print(json.dumps(payload, default=_json_default, sort_keys=True), file=self.stream, flush=True)
        elif self.mode == "text":
            suffix = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
            print(f"[site build] {message}{(' ' + suffix) if suffix else ''}", file=self.stream, flush=True)
        elif self.mode == "tqdm":
            suffix = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
            tqdm.write(f"[site build] {message}{(' ' + suffix) if suffix else ''}", file=self.stream)

    def phase(self, message: str, **fields: object) -> None:
        self.emit("phase", message, **fields)

    def task(self, label: str, total: int | None = None) -> ProgressTask:
        return ProgressTask(self, label, total)


def make_progress_reporter(*, progress_format: str = "auto", quiet: bool = False) -> ProgressReporter:
    return ProgressReporter(progress_format=progress_format, quiet=quiet)
