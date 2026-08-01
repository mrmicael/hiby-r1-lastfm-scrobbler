"""Logging that is useful when something goes wrong at 2am with a bricked DAP.

Two audiences. The GUI pane gets readable Portuguese; the log file gets the
same lines plus every command verbatim, so the whole install can be redone by
hand from the file alone. That is the point of the file — not diagnostics for
me, a transcript for the user.
"""

from __future__ import annotations

import datetime as _dt
import os
import platform
import sys
import threading
from typing import Callable, Optional

INFO = "info"
STEP = "step"
CMD = "cmd"
OUT = "out"
OK = "ok"
WARN = "warn"
ERROR = "error"
DRY = "dry"

_PREFIX = {
    INFO: "    ",
    STEP: "==> ",
    CMD: "  $ ",
    OUT: "  | ",
    OK: "  + ",
    WARN: "  ! ",
    ERROR: "  X ",
    DRY: " ~$ ",
}


class Log:
    """Fan-out logger. Thread-safe because work runs off the Tk thread."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._sinks: list[Callable[[str, str], None]] = []
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8", buffering=1)
        self._header()

    def _header(self) -> None:
        self.raw("")
        self.raw("=" * 78)
        self.raw(f"session started {_dt.datetime.now().isoformat(timespec='seconds')}")
        self.raw(f"host      {platform.platform()}")
        self.raw(f"python    {sys.version.split()[0]} ({sys.executable})")
        self.raw(f"cwd       {os.getcwd()}")
        self.raw("=" * 78)

    # -- sinks ---------------------------------------------------------------

    def add_sink(self, fn: Callable[[str, str], None]) -> None:
        with self._lock:
            self._sinks.append(fn)

    def remove_sink(self, fn: Callable[[str, str], None]) -> None:
        with self._lock:
            if fn in self._sinks:
                self._sinks.remove(fn)

    # -- emit ----------------------------------------------------------------

    def raw(self, text: str) -> None:
        with self._lock:
            self._fh.write(text + "\n")

    def write(self, level: str, text: str) -> None:
        stamp = _dt.datetime.now().strftime("%H:%M:%S")
        for line in (text or "").splitlines() or [""]:
            self.raw(f"{stamp} {_PREFIX.get(level, '    ')}{line}")
        with self._lock:
            sinks = list(self._sinks)
        for sink in sinks:
            try:
                sink(level, text)
            except Exception:  # a broken widget must never stop the install
                pass

    def info(self, text: str) -> None:
        self.write(INFO, text)

    def step(self, text: str) -> None:
        self.write(STEP, text)

    def cmd(self, text: str) -> None:
        self.write(CMD, text)

    def dry(self, text: str) -> None:
        self.write(DRY, text)

    def out(self, text: str) -> None:
        self.write(OUT, text)

    def ok(self, text: str) -> None:
        self.write(OK, text)

    def warn(self, text: str) -> None:
        self.write(WARN, text)

    def error(self, text: str) -> None:
        self.write(ERROR, text)

    def close(self) -> None:
        try:
            self.raw(f"session ended {_dt.datetime.now().isoformat(timespec='seconds')}")
            self._fh.close()
        except Exception:
            pass


_default: Optional[Log] = None


def default_log_path(base_dir: str) -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join(base_dir, "registros", f"sessao-{stamp}.log")


def get_log() -> Log:
    if _default is None:
        raise RuntimeError("log not initialised")
    return _default


def init_log(path: str) -> Log:
    global _default
    _default = Log(path)
    return _default
