"""Cross-compiles a static curl for the R1, from the projects' own sources.

The R1 has no usable TLS client of its own — busybox wget offers only legacy
ciphers, and the Last.fm API drops that handshake — so talking to the API from
the device needs a curl that came from somewhere. This builds one, on the
user's own machine, from curl.se and the Mbed-TLS releases. Nothing is
downloaded as a ready-made binary: a program that will run as root on someone's
player is not something to fetch from a stranger.

What is built targets **musl, not glibc**, and that is the important decision:
a "static" glibc binary still ``dlopen``s ``libnss_dns.so.2`` inside
``getaddrinfo``, so it cannot resolve a hostname on a device without matching
NSS modules. musl resolves in-process and links cleanly static.

The result is verified on the real device before being trusted: it has to pass
the ELF gate here, and the daemon refuses to send anything if the certificate
bundle is missing rather than handing over a session key unverified.
"""

from __future__ import annotations


import os
import shlex
import shutil
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .applog import Log
from .compilar import escolher_alvo, zig_disponivel
from .idioma import t
from .net import download
from .runner import IS_WINDOWS, InstallerError, Runner

# As fontes vêm dos sites oficiais dos dois projetos, e o digest é conferido
# no download. Nada é hospedado neste repositório.
# O pacote de certificados raiz que o projeto curl publica. Sem ele o R1 não
# tem como conferir que o servidor do outro lado é mesmo o Last.fm.
CACERT_URL = "https://curl.se/ca/cacert.pem"
CURL_SRC_URL = "https://curl.se/download/curl-8.11.1.tar.gz"
MBEDTLS_SRC_URL = (
    "https://github.com/Mbed-TLS/mbedtls/releases/download/"
    "mbedtls-3.6.2/mbedtls-3.6.2.tar.bz2"
)

# A escolha do alvo (mipsel-linux-musleabihf e companhia) mora em compilar.py,
# junto com o motivo de cada um estar naquela ordem.


@dataclass
class BuildResult:
    ok: bool
    artifact: Optional[str]
    log_tail: str = ""
    script_path: str = ""
    stage: str = ""
    log_path: str = ""
    hint: str = ""


def _diagnose_curl_failure(output: str) -> str:
    """Turn the usual cross-build failures into something actionable."""
    low = output.lower()
    hints: list[str] = []
    if "cannot exec" in low and ("bzip2" in low or "lbzip2" in low):
        hints.append(t("cb.hint.bz2"))
    if "unable to find static system library" in low:
        hints.append(t("cb.hint.staticlib"))
    elif "no acceptable c compiler" in low or "c compiler cannot create" in low:
        hints.append(t("cb.hint.nocc"))
    if "unknown target" in low or "unsupported target" in low:
        hints.append(t("cb.hint.target"))
    if "libpsl" in low:
        hints.append(t("cb.hint.libpsl"))
    for tool in ("make", "perl", "cc", "ar", "ranlib", "sed", "awk"):
        if f"{tool}: not found" in low or f"{tool}: command not found" in low:
            hints.append(t("cb.hint.tool", ferramenta=tool))
    if "aclocal" in low or "autoreconf" in low or "automake" in low:
        hints.append(t("cb.hint.autotools"))
    if not hints:
        hints.append(t("cb.hint.unknown"))
    return "\n\n".join(hints)


class PosixWorkspace:
    """A directory the POSIX side can build in, wherever that side lives."""

    def __init__(self, runner: Runner, log: Log, host_root: str, name: str):
        self.runner = runner
        self.log: Log = log
        self.host_dir = os.path.join(host_root, name)
        os.makedirs(self.host_dir, exist_ok=True)
        self._posix_dir: Optional[str] = None
        self.name = name

    @property
    def posix_dir(self) -> str:
        if not IS_WINDOWS:
            return self.host_dir
        if self._posix_dir is None:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            # Resolve the home directory with `cd && pwd` rather than $HOME:
            # inline scripts through wsl.exe have their $VAR substituted before
            # sh runs. See Runner.posix.
            home = self.runner.posix("cd && pwd", mutating=False, quiet=True,
                                     timeout=120).stdout.strip().splitlines()
            base = home[-1].strip() if home else ""
            if not base:
                raise InstallerError(t("cb.err.home.title"),
                                     t("cb.err.home.body"))
            remote = f"{base}/.cache/r1lastfm/{self.name}-{stamp}"
            self.runner.posix(f"mkdir -p {shlex.quote(remote)}", check=True,
                              timeout=120)
            self._posix_dir = remote
        return self._posix_dir

    def send(self, host_path: str, remote_name: Optional[str] = None) -> str:
        """Copy a host file into the workspace, returning its POSIX path."""
        target = f"{self.posix_dir}/{remote_name or os.path.basename(host_path)}"
        if not IS_WINDOWS:
            if os.path.abspath(host_path) != os.path.abspath(target):
                shutil.copy2(host_path, target)
            return target
        src = self.runner.to_posix_path(os.path.abspath(host_path))
        self.runner.posix(f"cp -f {shlex.quote(src)} {shlex.quote(target)}",
                          check=True, timeout=900)
        return target

    def send_tree(self, host_dir: str, remote_name: str) -> str:
        target = f"{self.posix_dir}/{remote_name}"
        if not IS_WINDOWS:
            if os.path.abspath(host_dir) != os.path.abspath(target):
                shutil.copytree(host_dir, target, dirs_exist_ok=True)
        else:
            src = self.runner.to_posix_path(os.path.abspath(host_dir))
            self.runner.posix(
                f"rm -rf {shlex.quote(target)} && "
                f"cp -a {shlex.quote(src)} {shlex.quote(target)}",
                check=True, timeout=1800,
            )
        self.normalise_shell_scripts(target)
        return target

    def normalise_shell_scripts(self, directory: str) -> None:
        """Strip CR from *.sh under ``directory``.

        A tree that came off a Windows checkout can carry CRLF, and dash reads
        ``set -e\\r`` as an illegal option — the failure is
        "build.sh: 3: set: Illegal option -", which points nowhere near line
        endings. Release tarballs are extracted by Python's tarfile and keep LF,
        so this only matters for a git clone; it costs one command, and the
        alternative is a baffling error.
        """
        script = (
            'set -e\n'
            f'cd {shlex.quote(directory)}\n'
            'find . -type f -name "*.sh" -print | while IFS= read -r f; do\n'
            '  if od -c "$f" | grep -q "\\\\r"; then\n'
            '    sed -i "s/\\r$//" "$f"\n'
            '    echo "normalizado: $f"\n'
            '  fi\n'
            'done\n'
        )
        res = self.runner.posix_script(script, name="crlf", quiet=True,
                                       timeout=300)
        if not res.ok:
            # Not fatal — the tree may already be fine — but silence here once
            # hid a script the POSIX side could not even read.
            self.log.warn(t("cb.crlf_warn"))
            return
        for line in res.stdout.splitlines():
            if line.startswith("normalizado:"):
                self.log.info(t("cb.crlf_fixed",
                                arquivo=line.split(":", 1)[1].strip()))

    def retrieve(self, posix_path: str, host_path: str) -> str:
        if not IS_WINDOWS:
            if os.path.abspath(posix_path) != os.path.abspath(host_path):
                shutil.copy2(posix_path, host_path)
            return host_path
        os.makedirs(os.path.dirname(host_path) or ".", exist_ok=True)
        dest = self.runner.to_posix_path(os.path.abspath(host_path))
        self.runner.posix(f"cp -f {shlex.quote(posix_path)} {shlex.quote(dest)}",
                          check=True, timeout=900)
        return host_path

    def write_script(self, filename: str, body: str) -> tuple[str, str]:
        host_path = os.path.join(self.host_dir, filename)
        with open(host_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        posix_path = self.send(host_path)
        self.runner.posix(f"chmod +x {shlex.quote(posix_path)}", check=False)
        return host_path, posix_path


# --------------------------------------------------------------------------
# zig
# --------------------------------------------------------------------------


def _missing_build_tools(runner: Runner) -> list[str]:
    """Which of the tools the curl build needs are absent.

    Zig supplies the compiler and the linker, so this is a short list: make to
    drive both builds, and perl because mbedTLS's and curl's build machinery
    reaches for it. Everything else comes from the Zig tarball.
    """
    needed = ("make", "perl")
    probe = "; ".join(
        f"command -v {tool} >/dev/null 2>&1 && echo have:{tool} || echo miss:{tool}"
        for tool in needed
    )
    res = runner.posix(probe, mutating=False, quiet=True, timeout=180)
    return [line.split(":", 1)[1] for line in res.stdout.splitlines()
            if line.strip().startswith("miss:")]


def ensure_build_tools(runner: Runner, log: Log) -> None:
    """Install make/perl inside the distribution if they are missing.

    A bare WSL Ubuntu has neither, and the failure is one line deep in a build
    log — "make: not found" — long after the user has committed to a 20-minute
    wait. Installed as the distro's root, which needs no password.
    """
    missing = _missing_build_tools(runner)
    if not missing:
        return
    log.warn(t("cb.tools_missing", lista=", ".join(missing)))
    if not IS_WINDOWS:
        raise InstallerError(
            t("cb.err.tools.title", lista=", ".join(missing)),
            t("cb.err.tools.body"))
    log.info(t("cb.tools_installing"))
    res = runner.run(
        ["wsl.exe", "-d", runner.wsl_distro or "", "-u", "root", "--", "sh", "-c",
         "export DEBIAN_FRONTEND=noninteractive; apt-get update && "
         "apt-get install -y make perl"],
        timeout=1800,
    )
    still = _missing_build_tools(runner)
    if still:
        raise InstallerError(
            t("cb.err.install.title", lista=", ".join(still)),
            t("cb.err.install.body", saida=res.output[-2000:]))
    log.ok(t("cb.tools_ok"))


def _posix_can_read(runner: Runner, archive_suffix: str) -> bool:
    """Does the POSIX side have a decompressor for this archive type?

    Asked because GNU tar delegates: on Ubuntu it reaches for ``lbzip2`` for a
    .bz2 and dies with "lbzip2: Cannot exec: No such file or directory" when
    that parallel variant is not installed — even though plain bzip2 might be.
    """
    tools = {
        ".bz2": ("lbzip2", "bzip2", "pbzip2"),
        ".xz": ("xz",),
        ".gz": ("gzip",),
    }.get(archive_suffix, ())
    if not tools:
        return True
    probe = " || ".join(f"command -v {ferr} >/dev/null 2>&1"
                        for ferr in tools)
    res = runner.posix(f"({probe}) && echo SIM || echo NAO",
                       mutating=False, quiet=True, timeout=120)
    return "SIM" in res.stdout


def ensure_gzip_tarball(local_path: str, cache_dir: str, runner: Runner,
                        log: Log) -> str:
    """Return a tarball the POSIX side can definitely unpack.

    mbedTLS publishes its release only as ``.tar.bz2``, and whether tar can read
    that depends on which bzip2 variant happens to be installed. Rather than
    apt-installing a package as root just to unpack one file, the archive is
    transcoded to ``.tar.gz`` here with the standard library — Python reads bz2
    and xz natively, and gzip is the one format tar never has trouble with.

    A no-op when the archive is already readable.
    """
    lower = local_path.lower()
    suffix = ".bz2" if lower.endswith(".bz2") else ".xz" if lower.endswith(".xz") else ""
    if not suffix:
        return local_path
    if _posix_can_read(runner, suffix):
        return local_path

    base = os.path.basename(local_path)
    stem = base[: -len(suffix)] if base.lower().endswith(suffix) else base
    if not stem.endswith(".tar"):
        stem += ".tar"
    target = os.path.join(cache_dir, "src", stem + ".gz")

    if os.path.isfile(target) and os.path.getsize(target) > 0:
        log.info(t("cb.targz_cached", arquivo=base))
        return target

    log.warn(t("cb.converting", sufixo=suffix, arquivo=base))
    import bz2
    import gzip
    import lzma
    import shutil as _shutil

    opener = bz2.open if suffix == ".bz2" else lzma.open
    os.makedirs(os.path.dirname(target), exist_ok=True)
    partial = target + ".part"
    try:
        with opener(local_path, "rb") as src, gzip.open(partial, "wb", 1) as out:
            _shutil.copyfileobj(src, out, 4 << 20)
        os.replace(partial, target)
    except OSError as exc:
        try:
            os.remove(partial)
        except OSError:
            pass
        raise InstallerError(t("cb.err.targz", arquivo=base), str(exc))
    log.ok(t("cb.converted", arquivo=os.path.basename(target),
               bytes=f"{os.path.getsize(target):,}"))
    return target


CURL_SCRIPT = r"""#!/bin/sh
# Cross-compile a static curl for the HiBy R1 (MIPS32 little-endian).
#
# musl, not glibc, and on purpose: a statically linked glibc binary still
# dlopen()s libnss_dns.so.2 from inside getaddrinfo, so it cannot resolve a
# hostname on a device that has no matching NSS modules. musl resolves in-tree.
#
# Generated by the HiBy R1 installer. Safe to run again by hand.
set -e

TARGET="__TARGET__"
ROOT="__ROOT__"
PREFIX="$ROOT/prefix"
CURL_TAR="__CURL_TAR__"
MBED_TAR="__MBED_TAR__"
CURL_URL="__CURL_URL__"
MBED_URL="__MBED_URL__"
ZIG_DIR="__ZIG_DIR__"
JOBS="$(nproc 2>/dev/null || echo 2)"

# Re-runnable by hand: if the installer's copies are gone, fetch them again,
# and put the installer's own zig on PATH if it is not already there.
[ -n "$ZIG_DIR" ] && [ -d "$ZIG_DIR" ] && PATH="$ZIG_DIR:$PATH" && export PATH

banner() { echo ""; echo "=== $1 ==="; }

fetch() {
    # $1 = local file, $2 = url
    [ -s "$1" ] && return 0
    echo "baixando $(basename "$1")"
    if command -v curl >/dev/null 2>&1; then
        curl -fLo "$1" "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$1" "$2"
    else
        echo "sem curl nem wget para baixar $2" >&2
        return 1
    fi
}

cd "$ROOT"
mkdir -p "$PREFIX"

banner "ferramentas"
zig version
echo "alvo: $TARGET"
echo "jobs: $JOBS"

banner "fontes"
fetch "$CURL_TAR" "$CURL_URL"
fetch "$MBED_TAR" "$MBED_URL"
ls -la "$CURL_TAR" "$MBED_TAR"

banner "desempacotando"
rm -rf mbedtls-src curl-src
mkdir -p mbedtls-src curl-src
tar xf "$MBED_TAR" -C mbedtls-src --strip-components=1
tar xf "$CURL_TAR" -C curl-src --strip-components=1

export CC="zig cc -target $TARGET"
export AR="zig ar"
export RANLIB="zig ranlib"
export CFLAGS="-Os -fno-stack-protector"

banner "mbedtls"
cd "$ROOT/mbedtls-src"
make -j"$JOBS" lib CC="$CC" AR="$AR" CFLAGS="$CFLAGS -Ilibrary -Iinclude"
make install DESTDIR="$PREFIX"
ls -la "$PREFIX/lib" | head -20

banner "curl configure"
cd "$ROOT/curl-src"
./configure \
  --host=mipsel-linux-musl \
  --prefix="$ROOT/curl-install" \
  --with-mbedtls="$PREFIX" \
  --enable-static --disable-shared \
  --disable-ldap --disable-ldaps --disable-rtsp --disable-dict \
  --disable-telnet --disable-tftp --disable-pop3 --disable-imap \
  --disable-smtp --disable-gopher --disable-mqtt --disable-smb \
  --disable-manual --disable-docs --disable-libcurl-option \
  --without-libpsl --without-libidn2 --without-zlib --without-brotli \
  --without-zstd --without-nghttp2 --without-ngtcp2 --without-librtmp \
  CC="$CC" AR="$AR" RANLIB="$RANLIB" \
  CFLAGS="$CFLAGS" \
  CPPFLAGS="-I$PREFIX/include" \
  LDFLAGS="-static -L$PREFIX/lib"
# --disable-threaded-resolver USED to be here, and it must not come back.
#
# The reasoning was sound and the result was worse. By default curl resolves
# names in a pthread, and in a statically linked musl binary that thread never
# starts on this device — every request dies with
#   curl: (6) getaddrinfo() thread failed to start
# even though the device resolves names fine (busybox nslookup and ping work).
# Disabling the threaded resolver makes curl call getaddrinfo directly, which
# looks like the obvious fix.
#
# It is not. That build SEGFAULTS on every request — signal 11, before any
# network traffic, with or without TLS. Somebody who turned Wi-Fi sending on
# got exactly that:
#   Segmentation fault
#   CURL_FALHOU rc=139
# and there was nothing in the message to suggest the curl they had just spent
# half an hour compiling was the problem.
#
# So the threaded resolver stays, broken thread and all, and the DNS problem is
# worked around where it belongs: the daemon resolves the name with busybox
# nslookup and hands curl the address with --resolve. That path is proven — it
# is what every successful send from this project has gone through.
#
# The lesson is the same one the firmware patcher taught: a fix that was
# reasoned about is not a fix that was run. Whatever is built here is now smoke
# tested ON THE DEVICE before it is allowed to replace a working curl.
#
# Note: no LIBS= here on purpose. --with-mbedtls already adds the include and
# library paths and the -lmbedtls/-lmbedx509/-lmbedcrypto it needs. Passing LIBS
# by hand puts those libraries into configure's very first sanity check, before
# any -L is in play, and zig answers
#   error: unable to find static system library 'mbedtls' ... searched paths: none
# which autoconf reports as the maddeningly vague
#   error: C compiler cannot create executables

banner "curl make"
make -j"$JOBS"

banner "resultado"
ls -la src/curl
# It is a MIPS binary on an x86 host, so of course it does not run here. Asking
# anyway is a cheap way to confirm the loader rejects it for the right reason.
"$ROOT/curl-src/src/curl" --version 2>/dev/null \
    || echo "(não executa aqui, como esperado: é um binário MIPS)"
command -v file >/dev/null 2>&1 && file src/curl
cp -f src/curl "$ROOT/curl"
ls -la "$ROOT/curl"
echo "__BUILD_OK__"
"""


def build_static_curl(
    runner: Runner,
    log: Log,
    cache_dir: str,
    work_root: str,
    on_line: Optional[Callable[[str], None]] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> BuildResult:
    """Baixa as fontes, compila, e devolve o binário — uma vez só, por máquina."""
    if not runner.posix_available():
        raise InstallerError(t("cb.err.linux.title"), t("cb.err.linux.body"))
    if not zig_disponivel(runner):
        raise InstallerError(t("cb.err.zig.title"), t("cb.err.zig.body"))

    log.step(t("cb.step"))
    log.warn(t("cb.warn"))

    ensure_build_tools(runner, log)

    ws = PosixWorkspace(runner, log, work_root, "build-curl")
    target = escolher_alvo(runner, log)

    curl_tar = os.path.join(cache_dir, "src", os.path.basename(CURL_SRC_URL))
    mbed_tar = os.path.join(cache_dir, "src", os.path.basename(MBEDTLS_SRC_URL))
    download(CURL_SRC_URL, curl_tar, log=log, cancel=cancel, label="curl (fonte)")
    download(MBEDTLS_SRC_URL, mbed_tar, log=log, cancel=cancel, label="mbedTLS (fonte)")

    # mbedTLS ships only .tar.bz2, and tar's ability to read it depends on which
    # bzip2 variant is installed. Normalise before anything touches it.
    curl_tar = ensure_gzip_tarball(curl_tar, cache_dir, runner, log)
    mbed_tar = ensure_gzip_tarball(mbed_tar, cache_dir, runner, log)

    remote_curl = ws.send(curl_tar)
    remote_mbed = ws.send(mbed_tar)

    body = (CURL_SCRIPT
            .replace("__TARGET__", target)
            .replace("__ROOT__", ws.posix_dir)
            .replace("__CURL_TAR__", remote_curl)
            .replace("__MBED_TAR__", remote_mbed)
            .replace("__CURL_URL__", CURL_SRC_URL)
            .replace("__MBED_URL__", MBEDTLS_SRC_URL)
            .replace("__ZIG_DIR__", runner.posix_path_extra or ""))
    host_script, posix_script = ws.write_script("build_curl_mipsel.sh", body)
    log.info(t("cb.script_at", caminho=host_script))

    stage = {"name": "início"}

    def watch(line: str) -> None:
        if line.startswith("=== ") and line.endswith(" ==="):
            stage["name"] = line[4:-4]
        if on_line:
            on_line(line)

    res = runner.posix(f"sh {shlex.quote(posix_script)}", on_line=watch, timeout=7200)

    # The whole build output goes next to the script, so a failure can be read
    # in full instead of through the tail the dialog can show.
    log_path = os.path.join(ws.host_dir, "build_curl.log")
    try:
        with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"# alvo: {target}\n# script: {host_script}\n\n")
            fh.write(res.output)
        log.info(t("cb.log_at", caminho=log_path))
    except OSError:
        log_path = ""

    if not res.ok or "__BUILD_OK__" not in res.stdout:
        return BuildResult(
            False, None, res.output[-6000:], script_path=host_script,
            stage=stage["name"], log_path=log_path,
            hint=_diagnose_curl_failure(res.output),
        )

    host_curl = os.path.join(ws.host_dir, "curl")
    ws.retrieve(f"{ws.posix_dir}/curl", host_curl)
    if not runner.dry_run and not os.path.isfile(host_curl):
        return BuildResult(False, None, t("cb.no_artifact"),
                           script_path=host_script, stage=t("cb.stage.copy"),
                           log_path=log_path)
    log.ok(t("cb.done", caminho=host_curl))
    log.info(t("cb.done.note", alvo=target))
    return BuildResult(True, host_curl, script_path=host_script,
                       log_path=log_path)
