"""Download and install Zig, from ziglang.org's own release index.

Zig is the cross-compiler both projects use, and it is the one dependency that
genuinely installs itself: it is a single self-contained tarball with no
toolchain to configure. So rather than telling the user to go fetch it, this
fetches it — verifying the SHA256 that ziglang.org publishes alongside each
tarball, which is the whole reason automating this is defensible at all.

Where it lands matters. The builds run on the POSIX side (inside WSL on
Windows), so Zig has to be a **Linux** build living inside the distribution,
not a zig.exe on the Windows PATH. It is unpacked under the distro's own
``$HOME`` and reached by prepending one directory to PATH, so nothing outside
this installer's own folder is touched and no system package manager is
involved.

Version choice is deliberately the user's. ``app/build.sh`` was written against
whatever Zig its author had, and Zig still makes breaking changes between minor
releases; when a build fails on the newest version, trying an older one is the
first thing to do.
"""

from __future__ import annotations

import os
import posixpath
import re
import shlex
from dataclasses import dataclass
from typing import Callable, Optional

from .applog import Log
from .idioma import t
from .net import download, fetch_json
from .runner import IS_WINDOWS, InstallerError, Runner

INDEX_URL = "https://ziglang.org/download/index.json"

# Where Zig is unpacked, relative to the POSIX side's $HOME. Kept inside our
# own directory so uninstalling is "delete this folder".
INSTALL_SUBDIR = ".local/share/r1lastfm/zig"

PROBE_TIMEOUT = 120.0


@dataclass
class ZigRelease:
    version: str
    date: str
    target: str
    tarball: str
    shasum: str
    size: int

    @property
    def filename(self) -> str:
        return os.path.basename(self.tarball)

    def label(self) -> str:
        return f"{self.version}   ({self.date})   {self.size / 1e6:.0f} MB"


# --------------------------------------------------------------------------
# which build do we need
# --------------------------------------------------------------------------


def posix_target_key(runner: Runner, log: Log) -> str:
    """The index.json key for the platform the compiler will actually run on.

    On Windows that is the WSL distribution, not Windows — the builds are
    driven through ``sh``, and a zig.exe would be useless to ``build.sh``.
    """
    probe = runner.posix("uname -s; uname -m", mutating=False, quiet=True,
                         timeout=PROBE_TIMEOUT)
    parts = probe.stdout.split()
    if len(parts) < 2:
        raise InstallerError(t("zs.err.uname.title"),
                             t("zs.err.uname.body", saida=probe.output))
    system, machine = parts[0].lower(), parts[1].lower()

    if "linux" in system:
        os_key = "linux"
    elif "darwin" in system:
        os_key = "macos"
    else:
        raise InstallerError(t("zs.err.os.title", sistema=parts[0]),
                             t("zs.err.os.body"))

    arch_map = {
        "x86_64": "x86_64", "amd64": "x86_64",
        "aarch64": "aarch64", "arm64": "aarch64",
        "armv7l": "arm", "riscv64": "riscv64", "i686": "x86", "i386": "x86",
    }
    arch = arch_map.get(machine)
    if not arch:
        raise InstallerError(t("zs.err.arch.title", maquina=machine),
                             t("zs.err.arch.body"))
    key = f"{arch}-{os_key}"
    log.info(t("zs.target", alvo=key))
    return key


# --------------------------------------------------------------------------
# the index
# --------------------------------------------------------------------------


def _version_sort_key(version: str) -> tuple:
    nums = [int(n) for n in re.findall(r"\d+", version)[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def fetch_releases(target: str, log: Log, include_master: bool = False) -> list[ZigRelease]:
    """Stable releases carrying a build for ``target``, newest first."""
    log.info(t("zs.asking"))
    data = fetch_json(INDEX_URL)
    if not isinstance(data, dict):
        raise InstallerError(t("zs.err.index"), INDEX_URL)

    out: list[ZigRelease] = []
    for version, blob in data.items():
        if not isinstance(blob, dict):
            continue
        if version == "master" and not include_master:
            continue          # a nightly is not what an installer should pick
        build = blob.get(target)
        if not isinstance(build, dict) or not build.get("tarball"):
            continue
        shasum = str(build.get("shasum") or "")
        if len(shasum) != 64:
            log.warn(t("zs.no_sha", versao=version))
            continue
        try:
            size = int(build.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        out.append(ZigRelease(
            version=blob.get("version", version) if version == "master" else version,
            date=str(blob.get("date") or ""),
            target=target,
            tarball=str(build["tarball"]),
            shasum=shasum,
            size=size,
        ))

    out.sort(key=lambda r: _version_sort_key(r.version), reverse=True)
    if not out:
        raise InstallerError(t("zs.err.norelease.title", alvo=target),
                             t("zs.err.norelease.body"))
    log.ok(t("zs.found", n=len(out), recente=out[0].version))
    return out


# --------------------------------------------------------------------------
# install / locate
# --------------------------------------------------------------------------


def _posix_home(runner: Runner) -> str:
    # `cd` with no argument goes to the home directory and `pwd` prints it —
    # no shell variable involved, which matters because an inline script's
    # $VAR is substituted by wsl.exe before sh runs. See Runner.posix.
    probe = runner.posix("cd && pwd", mutating=False, quiet=True,
                         timeout=PROBE_TIMEOUT)
    home = probe.stdout.strip().splitlines()[-1].strip() if probe.stdout.strip() else ""
    if not home:
        raise InstallerError(
            t("zs.err.home.wsl") if IS_WINDOWS else t("zs.err.home.plain"),
            t("zs.err.home.body", saida=probe.output))
    return home


def install_root(runner: Runner) -> str:
    return f"{_posix_home(runner)}/{INSTALL_SUBDIR}"


def _locate_binary(runner: Runner, root: str) -> Optional[str]:
    """Absolute path of an executable ``zig`` under ``root``, or None.

    ``find`` rather than a shell loop: a ``for``/``$d`` loop is exactly the
    construct wsl.exe breaks inline, and it breaks it silently — the loop
    iterates the right number of times with an empty variable.
    """
    res = runner.posix(
        f"find {shlex.quote(root)} -maxdepth 2 -type f -name zig -perm -u+x",
        mutating=False, quiet=True, timeout=PROBE_TIMEOUT,
    )
    paths = [ln.strip() for ln in res.stdout.splitlines()
             if ln.strip().startswith("/") and ln.strip().endswith("/zig")]
    return paths[0] if paths else None


def find_installed(runner: Runner, log: Optional[Log] = None) -> Optional[tuple[str, str]]:
    """Look for a Zig this installer put there. Returns (dir, version) or None."""
    try:
        root = install_root(runner)
    except InstallerError:
        return None
    binary = _locate_binary(runner, root)
    if not binary:
        return None
    directory = posixpath.dirname(binary)
    check = runner.posix(f"{shlex.quote(binary)} version", mutating=False,
                         quiet=True, timeout=PROBE_TIMEOUT)
    version = check.stdout.strip().splitlines()[-1].strip() if check.stdout.strip() else ""
    if not check.ok or not version:
        return None
    if log:
        log.ok(t("zs.already", versao=version, onde=directory))
    return directory, version


def _ensure_xz(runner: Runner, log: Log) -> None:
    """Zig ships .tar.xz; make sure the extractor can read it."""
    res = runner.posix("command -v xz >/dev/null 2>&1 && echo SIM || echo NAO",
                       mutating=False, quiet=True, timeout=PROBE_TIMEOUT)
    if "SIM" in res.stdout:
        return
    if not IS_WINDOWS:
        raise InstallerError(t("zs.err.xz.title"), t("zs.err.xz.body"))
    log.warn(t("zs.installing_xz"))
    runner.run(
        ["wsl.exe", "-d", runner.wsl_distro or "", "-u", "root", "--", "sh", "-c",
         "export DEBIAN_FRONTEND=noninteractive; apt-get update && "
         "apt-get install -y xz-utils"],
        check=True, timeout=900,
    )


def install(
    runner: Runner,
    log: Log,
    release: ZigRelease,
    cache_dir: str,
    *,
    progress: Optional[Callable[[int, int], None]] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> tuple[str, str]:
    """Download, verify and unpack Zig. Returns (directory, version)."""
    if not runner.posix_available():
        raise InstallerError(t("zs.err.linux.title"), t("zs.err.linux.body"))

    log.step(t("zs.installing", versao=release.version, alvo=release.target))
    log.info(t("zs.sha_note"))
    log.info(f"    {release.shasum}")

    local = os.path.join(cache_dir, "zig", release.filename)
    download(
        release.tarball, local, log=log,
        progress=progress, cancel=cancel,
        expect_sha256=release.shasum,
        expect_size=release.size or None,
        label=release.filename,
    )

    _ensure_xz(runner, log)

    root = install_root(runner)
    runner.posix(f"mkdir -p {shlex.quote(root)}", check=True, timeout=PROBE_TIMEOUT)

    # Move the tarball to the POSIX side. Reading from /mnt/c is fine — it is
    # only the *writing* of a rootfs that drvfs cannot do faithfully.
    if IS_WINDOWS:
        src = runner.to_posix_path(os.path.abspath(local))
        remote_tar = f"{root}/{release.filename}"
        log.info(t("zs.copying"))
        runner.posix(f"cp -f {shlex.quote(src)} {shlex.quote(remote_tar)}",
                     check=True, timeout=1800)
    else:
        remote_tar = os.path.abspath(local)

    log.info(t("zs.unpacking"))
    res = runner.posix(
        f"tar -xf {shlex.quote(remote_tar)} -C {shlex.quote(root)}",
        timeout=1800,
    )
    if not res.ok:
        raise InstallerError(t("zs.err.unpack.title"),
                             t("zs.err.unpack.body", onde=root,
                               saida=res.output[-3000:]))

    if runner.dry_run:
        return f"{root}/zig-{release.target}-{release.version}", release.version

    # The directory name has changed shape across Zig releases
    # (zig-linux-x86_64-0.13.0 vs zig-x86_64-linux-0.16.0), so the binary is
    # located rather than assumed.
    binary = _locate_binary(runner, root)
    if not binary:
        raise InstallerError(t("zs.err.nobin.title"),
                             t("zs.err.nobin.body", onde=root,
                               saida=res.output[-2000:]))
    directory = posixpath.dirname(binary)

    check = runner.posix(f"{shlex.quote(binary)} version",
                         mutating=False, timeout=PROBE_TIMEOUT)
    version = check.stdout.strip().splitlines()[-1].strip() if check.stdout.strip() else ""
    if not check.ok or not version:
        raise InstallerError(t("zs.err.norun.title"),
                             t("zs.err.norun.body", onde=directory,
                               saida=check.output[-2000:]))

    # The tarball is ~50 MB and serves no purpose once unpacked; the cached
    # copy on the host side stays, so a reinstall does not re-download.
    runner.posix(f"rm -f {shlex.quote(remote_tar)}")

    log.ok(t("zs.done", versao=version, onde=directory))
    log.info(t("zs.where_note"))
    return directory, version


def uninstall(runner: Runner, log: Log) -> None:
    """Remove only what we unpacked."""
    root = install_root(runner)
    if INSTALL_SUBDIR not in root:
        log.warn(t("zs.odd_path"))
        return
    log.step(t("zs.removing"))
    runner.posix(f"rm -rf {shlex.quote(root)}", timeout=600)
    log.ok(t("zs.removed"))
