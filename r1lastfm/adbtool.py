"""ADB against the R1, with the one gotcha this device has spelled out.

ADB and USB-DAC share the single USB gadget controller and are mutually
exclusive by *USB working mode*. If the player is set to DAC there is no adbd to
talk to, and the symptom is an empty ``adb devices`` list that looks exactly
like a bad cable. Both mod releases document this; the installer says it out
loud instead of letting the user chase a cable.
"""

from __future__ import annotations

import os
import posixpath
import re
from dataclasses import dataclass
from typing import Callable, Optional

from .applog import Log
from .idioma import t
from .runner import InstallerError, Result, Runner

def ajuda_usb() -> str:
    """O que fazer quando o aparelho não aparece.

    É função, e não constante, porque o idioma pode mudar durante a execução:
    uma constante montada na importação ficaria congelada na língua em que o
    programa abriu.
    """
    return t("adb.usb_help")


@dataclass
class Device:
    serial: str
    state: str
    extra: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "device"

    def describe(self) -> str:
        names = {
            "device": "pronto",
            "unauthorized": "não autorizado",
            "offline": "offline",
            "recovery": "recovery",
            "no permissions": "sem permissão",
        }
        return f"{self.serial}  —  {names.get(self.state, self.state)}"


class Adb:
    def __init__(self, runner: Runner, log: Log, adb_path: str):
        self.runner = runner
        self.log = log
        self.adb_path = adb_path
        self.serial: Optional[str] = None

    # -- plumbing ------------------------------------------------------------

    def _base(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def raw(self, args: list[str], *, mutating: bool = True, check: bool = False,
            timeout: Optional[float] = 180,
            on_line: Optional[Callable[[str], None]] = None) -> Result:
        return self.runner.run(self._base() + args, mutating=mutating, check=check,
                               timeout=timeout, on_line=on_line)

    # -- discovery -----------------------------------------------------------

    def devices(self) -> list[Device]:
        res = self.runner.run([self.adb_path, "devices", "-l"], mutating=False,
                              timeout=60)
        found: list[Device] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            if line.startswith("*"):  # "* daemon started successfully *"
                continue
            m = re.match(r"^(\S+)\s+(device|unauthorized|offline|recovery|no permissions\S*)"
                         r"\s*(.*)$", line)
            if m:
                found.append(Device(m.group(1), m.group(2).split()[0], m.group(3)))
        return found

    def require_device(self) -> Device:
        devs = self.devices()
        ready = [d for d in devs if d.ready]
        if ready:
            self.serial = ready[0].serial
            return ready[0]
        if any(d.state == "unauthorized" for d in devs):
            raise InstallerError(t("adb.err.unauth.title"),
                                 t("adb.err.unauth.body"))
        if any(d.state == "offline" for d in devs):
            raise InstallerError(t("adb.err.offline.title"),
                                 t("adb.err.offline.body"))
        raise InstallerError(t("adb.err.nodevice"), ajuda_usb())

    def start_server(self) -> None:
        self.runner.run([self.adb_path, "start-server"], mutating=False, timeout=60)

    def kill_server(self) -> None:
        self.runner.run([self.adb_path, "kill-server"], timeout=60)

    # -- shell ---------------------------------------------------------------

    def shell(self, command: str, *, mutating: bool = True, check: bool = False,
              timeout: float = 180) -> Result:
        return self.raw(["shell", command], mutating=mutating, check=check,
                        timeout=timeout)

    def remote_exists(self, path: str) -> bool:
        res = self.shell(f"[ -e {_q(path)} ] && echo SIM || echo NAO", mutating=False)
        return "SIM" in res.stdout

    def remote_listing(self, path: str) -> str:
        res = self.shell(f"ls -l {_q(path)} 2>/dev/null", mutating=False)
        return res.stdout.strip()

    def mkdir(self, path: str) -> None:
        self.shell(f"mkdir -p {_q(path)}", check=True)

    def chmod(self, path: str, mode: str = "755") -> None:
        self.shell(f"chmod {mode} {_q(path)}", check=True)

    def free_space(self, path: str) -> str:
        res = self.shell(f"df -h {_q(path)} 2>/dev/null", mutating=False)
        return res.stdout.strip()

    # -- transfer ------------------------------------------------------------

    def push(self, local: str, remote: str, *, mode: Optional[str] = None,
             on_line: Optional[Callable[[str], None]] = None) -> None:
        if not self.runner.dry_run and not os.path.isfile(local):
            raise InstallerError(t("adb.err.nolocal"), f"{local}")
        res = self.raw(["push", local, remote], on_line=on_line, timeout=900)
        if not res.ok:
            raise InstallerError(
                t("adb.err.push", arquivo=os.path.basename(local)),
                _explain_push(res, remote))
        if mode:
            self.chmod(remote, mode)

    def sync_and_reboot(self) -> None:
        self.log.step(t("adb.rebooting"))
        self.shell("sync", check=False, timeout=120)
        # reboot cuts the connection, so a non-zero exit here is normal.
        self.raw(["shell", "reboot"], timeout=60)
        self.log.ok(t("adb.reboot_sent"))


def _q(path: str) -> str:
    """Quote for the device's busybox sh."""
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./-]+", path or ""):
        return path
    return "'" + (path or "").replace("'", "'\\''") + "'"


def _explain_push(res: Result, remote: str) -> str:
    low = res.output.lower()
    hints = []
    if "read-only file system" in low:
        hints.append(t("adb.push.readonly", pasta=posixpath.dirname(remote)))
    if "no space left" in low:
        hints.append(t("adb.push.nospace"))
    if "no such file or directory" in low:
        hints.append(t("adb.push.nodir"))
    if "device not found" in low or "no devices" in low:
        hints.append(ajuda_usb())
    return ("\n".join(hints) + "\n\n" if hints else "") + res.output[-2000:]
