"""Subprocess execution with a live log, a dry-run mode and WSL forwarding.

Two rules shape this module.

Every failure becomes an ``InstallerError`` carrying a sentence a person can
read. Nothing here is allowed to reach the GUI as a traceback — a stack trace
in the middle of a firmware flash tells the user nothing and frightens them.

Dry-run only suppresses commands that *change* something. Probes still run, so
a dry-run walkthrough shows the real device, the real card and the real
toolchain rather than a fiction.
"""

from __future__ import annotations

import itertools
import os
import shlex
import subprocess
import sys
import tempfile
import threading
from .idioma import t
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .applog import Log

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# Keeps console windows from flashing on Windows for every probe.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

_counter = itertools.count(1)

# No command may hang the worker thread forever. wsl.exe in particular can
# stall indefinitely when the VM is wedged, and a frozen worker takes the
# cancel button with it — the user is left with a window that does nothing.
# Operations that legitimately run longer (patching, cross-compiling, apt)
# pass an explicit timeout; everything else inherits this bound.
DEFAULT_TIMEOUT = 600.0


class InstallerError(Exception):
    """An error with a message meant for the user, not for a developer."""

    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class Cancelled(InstallerError):
    def __init__(self) -> None:
        super().__init__(t("run.cancelled"))


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str
    command: str
    skipped: bool = False

    @property
    def ok(self) -> bool:
        return self.code == 0

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" + self.stderr if self.stderr else "")).strip()

    def lines(self) -> list[str]:
        return [ln for ln in self.stdout.splitlines() if ln.strip()]


@dataclass
class Runner:
    """Runs commands on the host and, on Windows, inside a WSL distribution."""

    log: Log
    dry_run: bool = False
    wsl_distro: Optional[str] = None
    # Prepended to PATH for every POSIX-side command. This is how a Zig that
    # this installer unpacked becomes visible to the projects' own build.sh,
    # which calls a bare `zig cc` — without touching the user's shell profile
    # or any system directory.
    posix_path_extra: Optional[str] = None
    # Where posix_script() writes its temporary scripts. Set to the session's
    # work directory so a failed build leaves the script behind to re-run.
    script_dir: Optional[str] = None
    keep_scripts: bool = False
    _cancel: threading.Event = field(default_factory=threading.Event)
    # Path translation costs a wsl.exe round trip each time; the answer for a
    # given absolute path does not change during a session.
    _path_cache: dict = field(default_factory=dict)

    # -- cancellation --------------------------------------------------------

    def request_cancel(self) -> None:
        self._cancel.set()

    def clear_cancel(self) -> None:
        self._cancel.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def raise_if_cancelled(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    # -- host commands -------------------------------------------------------

    def run(
        self,
        cmd: Sequence[str],
        *,
        mutating: bool = True,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        check: bool = False,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        on_line: Optional[Callable[[str], None]] = None,
        quiet: bool = False,
        input_text: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Result:
        """Run ``cmd`` and stream its output into the log.

        ``mutating`` marks a command that changes the world; in dry-run those
        are logged and skipped. Read-only probes always run.
        """
        self.raise_if_cancelled()
        printable = " ".join(shlex.quote(c) for c in cmd)

        if self.dry_run and mutating:
            self.log.dry(printable)
            return Result(0, "", "", printable, skipped=True)

        if not quiet:
            self.log.cmd(printable)

        merged = dict(os.environ)
        if env:
            merged.update(env)

        try:
            proc = subprocess.Popen(
                list(cmd),
                cwd=cwd,
                env=merged,
                stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=_NO_WINDOW,
            )
        except FileNotFoundError:
            raise InstallerError(
                t("run.err.notfound.title", cmd=cmd[0]),
                t("run.err.notfound.body", cmd=cmd[0], linha=printable))
        except PermissionError:
            raise InstallerError(
                t("run.err.perm.title", cmd=cmd[0]),
                t("run.err.cmd", linha=printable))
        except OSError as exc:
            raise InstallerError(
                t("run.err.exec.title", cmd=cmd[0], erro=exc),
                t("run.err.cmd", linha=printable))

        if input_text is not None and proc.stdin:
            try:
                proc.stdin.write(input_text.encode(encoding))
                proc.stdin.close()
            except OSError:
                pass

        out_chunks: list[str] = []
        err_chunks: list[str] = []

        def pump(stream, sink: list[str], is_err: bool) -> None:
            for raw in iter(stream.readline, b""):
                text = raw.decode(encoding, errors="replace").rstrip("\r\n")
                sink.append(text)
                if not quiet:
                    self.log.out(text)
                if on_line and not is_err:
                    try:
                        on_line(text)
                    except Exception:
                        pass
            stream.close()

        threads = [
            threading.Thread(target=pump, args=(proc.stdout, out_chunks, False), daemon=True),
            threading.Thread(target=pump, args=(proc.stderr, err_chunks, True), daemon=True),
        ]
        for th in threads:
            th.start()

        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            for th in threads:
                th.join(timeout=2)
            raise InstallerError(
                t("run.err.timeout", segundos=f"{timeout:.0f}"),
                t("run.err.cmd", linha=printable))
        for th in threads:
            th.join(timeout=5)

        result = Result(code, "\n".join(out_chunks), "\n".join(err_chunks), printable)
        if check and code != 0:
            raise InstallerError(
                t("run.err.code.title", codigo=code),
                t("run.err.code.body", linha=printable,
                  saida=result.output[-4000:]))
        return result

    # -- POSIX side ----------------------------------------------------------

    def posix_available(self) -> bool:
        return (not IS_WINDOWS) or bool(self.wsl_distro)

    def posix(
        self,
        script: str,
        *,
        mutating: bool = True,
        check: bool = False,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        on_line: Optional[Callable[[str], None]] = None,
        quiet: bool = False,
    ) -> Result:
        """Run a ``/bin/sh`` script on Linux/macOS, or inside WSL on Windows.

        On Windows the whole snippet goes through ``wsl.exe -d <distro> -- sh -c``.
        The patcher cannot be split across the boundary: it imports pycdlib and
        calls unsquashfs in one process, and unsquashfs writing to a Windows
        drive through drvfs silently loses symlinks and ownership. The R1 rootfs
        is full of busybox symlinks, so a repack from drvfs is a brick.

        **Do not use shell-local variables in ``script``.** Passing a script
        inline through wsl.exe substitutes ``$NAME`` from the *environment*
        before ``sh`` ever sees it, so:

            x=abc; echo $x        ->  prints nothing
            for d in *; do ... $d ->  $d is empty on every iteration
            $1                    ->  empty

        while ``$HOME``/``$PATH`` expand (to the correct Linux values),
        and ``$(...)``, backticks, ``$((...))``, ``$?`` and ``$$`` survive.
        Measured, not guessed. Getting this wrong is quiet: the loop still
        runs the right number of times, it just does nothing useful.

        Anything needing a variable must go through :meth:`posix_script`,
        which writes the body to a file where ``sh`` expands normally.
        """
        if self.posix_path_extra:
            # The dollar is escaped on Windows so that *sh* expands PATH rather
            # than wsl.exe's interop layer. This is not cosmetic: WSL appends
            # the Windows PATH to the Linux one, that contains
            # "/mnt/c/Program Files/...", and a pre-expanded value with a space
            # in it splits the assignment — sh then tries to run
            # "Files/dotnet/:/mnt/c/Program" as a command. On a native POSIX
            # host there is no interop, so the dollar must stay bare or sh would
            # take it literally.
            dollar = r"\$PATH" if IS_WINDOWS else "$PATH"
            script = (f"PATH={shlex.quote(self.posix_path_extra)}:{dollar}; "
                      f"export PATH; {script}")

        if IS_WINDOWS:
            if not self.wsl_distro:
                raise InstallerError(t("run.err.nowsl.title"),
                                     t("run.err.nowsl.body"))
            cmd = ["wsl.exe", "-d", self.wsl_distro, "--", "sh", "-c", script]
        else:
            cmd = ["/bin/sh", "-c", script]
        return self.run(
            cmd,
            mutating=mutating,
            check=check,
            timeout=timeout,
            on_line=on_line,
            quiet=quiet,
        )

    def posix_script(
        self,
        body: str,
        *,
        name: str = "trecho",
        mutating: bool = True,
        check: bool = False,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        on_line: Optional[Callable[[str], None]] = None,
        quiet: bool = False,
    ) -> Result:
        """Run a shell script by writing it to a file, then executing the file.

        This is the only safe way to use shell variables on the POSIX side —
        see :meth:`posix` for what inline scripts do to them. The file is
        written on the host and, on Windows, read through /mnt; reading across
        drvfs is fine, it is only writing a *rootfs* that drvfs cannot do
        faithfully.
        """
        directory = self.script_dir or tempfile.gettempdir()
        os.makedirs(directory, exist_ok=True)
        host_path = os.path.join(
            directory, f"{name}-{os.getpid()}-{next(_counter)}.sh")
        with open(host_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("#!/bin/sh\n" + body.rstrip() + "\n")

        if not quiet:
            self.log.info(f"(script in file: {host_path})")
        posix_path = (self.to_posix_path(host_path) if IS_WINDOWS else host_path)
        if IS_WINDOWS and not self._posix_exists(posix_path):
            # Worth failing loudly: a script the POSIX side cannot read fails as
            # "No such file", and callers that only inspect the exit code then
            # report something unrelated — the target probe once concluded that
            # zig supported no MIPS targets at all for exactly this reason.
            raise InstallerError(
                t("run.err.script.title"),
                t("run.err.script.body", janela=host_path, posix=posix_path))
        try:
            return self.posix(f"sh {shlex.quote(posix_path)}", mutating=mutating,
                              check=check, timeout=timeout, on_line=on_line,
                              quiet=quiet)
        finally:
            if not self.keep_scripts:
                try:
                    os.remove(host_path)
                except OSError:
                    pass

    # -- path translation ----------------------------------------------------

    def _wslpath(self, windows_path: str) -> Optional[str]:
        res = self.run(
            ["wsl.exe", "-d", self.wsl_distro or "", "--", "wslpath", "-a", "-u",
             windows_path.replace("\\", "/")],
            mutating=False,
            quiet=True,
            timeout=120,
        )
        line = res.stdout.strip().splitlines()
        return line[-1].strip() if (res.ok and line) else None

    def _posix_exists(self, posix_path: str) -> bool:
        res = self.posix(
            f"[ -e {shlex.quote(posix_path)} ] && echo SIM || echo NAO",
            mutating=False, quiet=True, timeout=120,
        )
        return "SIM" in res.stdout

    def to_posix_path(self, windows_path: str) -> str:
        """Windows path -> path as seen inside the WSL distribution.

        ``wslpath`` translates text, which is not enough. A packaged (MSIX)
        application has ``%LOCALAPPDATA%`` redirected through a reparse point:
        Python writes to ``…\\Local\\HiByR1Installer\\cache\\src\\x`` and the
        bytes actually land in
        ``…\\Local\\Packages\\<pkg>\\LocalCache\\Local\\HiByR1Installer\\cache\\src\\x``.
        WSL's /mnt/<drive> sees the real filesystem, so the naive translation
        points at a file that is not there — "cp: cannot stat ...".

        Confusingly it works for *some* paths: the redirection is per-directory
        copy-on-write, so a folder that also exists at the literal location
        resolves fine and the failure looks random.

        ``os.path.realpath`` on Windows resolves the reparse point, so the
        resolved path is tried first and the literal one kept as a fallback.
        Preference goes to whichever the POSIX side can actually see — or, for a
        path being created, whichever has a visible parent directory.
        """
        if not IS_WINDOWS:
            return windows_path

        absolute = os.path.abspath(windows_path)
        resolved = os.path.realpath(absolute)
        candidates: list[str] = []
        for path in (resolved, absolute):
            if path not in candidates:
                candidates.append(path)

        cached = self._path_cache.get(absolute)
        if cached:
            return cached

        translated: list[tuple[str, str]] = []
        for candidate in candidates:
            posix = self._wslpath(candidate)
            if posix:
                translated.append((candidate, posix))
        if not translated:
            raise InstallerError(t("run.err.wslpath.title"),
                                 t("run.err.wslpath.body",
                                   caminho=windows_path))

        # The file already exists: pick the translation that can see it.
        for _candidate, posix in translated:
            if self._posix_exists(posix):
                self._path_cache[absolute] = posix
                return posix

        # It does not exist yet (a destination). Pick one whose parent does.
        for _candidate, posix in translated:
            parent = posix.rsplit("/", 1)[0] or "/"
            if self._posix_exists(parent):
                self._path_cache[absolute] = posix
                return posix

        chosen = translated[0][1]
        self.log.warn(t("run.warn.invisible", caminho=chosen))
        return chosen


def which(name: str) -> Optional[str]:
    """shutil.which, but tolerant of a PATH entry that no longer exists."""
    import shutil

    try:
        return shutil.which(name)
    except Exception:
        return None
