"""HTTP with a progress callback, digest checking and a resume-free cache.

Standard library only. Anything downloaded lands in the cache under its own
name and is re-verified on every run, so a partially written file from a
cancelled session can never be mistaken for a good one: the digest check fails
and it is fetched again.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from .applog import Log
from .idioma import t
from .runner import Cancelled, InstallerError

USER_AGENT = "r1lastfm/1.0 (HiBy R1 Last.fm scrobbler)"

ProgressFn = Callable[[int, int], None]  # (bytes_done, bytes_total or -1)


def _context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _open(url: str, timeout: float = 60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=timeout, context=_context())


def _friendly(url: str, exc: Exception) -> InstallerError:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 403:
            return InstallerError(t("net.err.403.title"),
                                  t("net.err.403.body", url=url))
        if exc.code == 404:
            return InstallerError(t("net.err.404.title"),
                                  t("net.err.url", url=url))
        return InstallerError(t("net.err.http.title", codigo=exc.code),
                              t("net.err.url", url=url))
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, ssl.SSLError):
            return InstallerError(
                t("net.err.tls.title"),
                t("net.err.url_reason", url=url, motivo=reason))
        return InstallerError(
            t("net.err.conn.title"),
            t("net.err.url_reason", url=url, motivo=reason))
    return InstallerError(t("net.err.generic", erro=exc),
                          t("net.err.url", url=url))


def fetch_bytes(url: str, timeout: float = 60, max_size: int = 32 << 20) -> bytes:
    try:
        with _open(url, timeout) as resp:
            data = resp.read(max_size + 1)
    except Exception as exc:
        raise _friendly(url, exc)
    if len(data) > max_size:
        raise InstallerError(t("net.err.toobig"), url)
    return data


def fetch_json(url: str, timeout: float = 60):
    raw = fetch_bytes(url, timeout)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallerError(t("net.err.badreply.title"),
                             t("net.err.badreply.body", url=url, erro=exc))


@dataclass
class Digests:
    md5: str
    sha256: str
    size: int

    def matches(self, md5: Optional[str] = None, sha256: Optional[str] = None,
                size: Optional[int] = None) -> bool:
        if md5 and self.md5.lower() != md5.lower():
            return False
        if sha256 and self.sha256.lower() != sha256.lower():
            return False
        if size is not None and self.size != size:
            return False
        return True


def digest_file(path: str, progress: Optional[ProgressFn] = None,
                cancel: Optional[Callable[[], bool]] = None) -> Digests:
    md5, sha = hashlib.md5(), hashlib.sha256()
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb") as fh:
        while True:
            if cancel and cancel():
                raise Cancelled()
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            md5.update(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return Digests(md5.hexdigest(), sha.hexdigest(), total)


def download(
    url: str,
    dest: str,
    *,
    log: Log,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[Callable[[], bool]] = None,
    expect_md5: Optional[str] = None,
    expect_sha256: Optional[str] = None,
    expect_size: Optional[int] = None,
    reuse_cache: bool = True,
    label: str = "",
) -> Digests:
    """Download ``url`` to ``dest``, verifying digests, reusing a good cache hit.

    Nothing is ever silently overwritten: an existing file is either verified
    and reused, or moved aside with a ``.bad`` suffix before the new download.
    """
    name = label or os.path.basename(dest)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)

    if reuse_cache and os.path.isfile(dest) and os.path.getsize(dest) > 0:
        log.info(t("net.cache.checking", nome=name))
        try:
            have = digest_file(dest, progress, cancel)
        except Cancelled:
            raise
        if have.matches(expect_md5, expect_sha256, expect_size):
            log.ok(t("net.cache.ok", nome=name, bytes=f"{have.size:,}",
                     sha=have.sha256[:16]))
            return have
        if expect_md5 or expect_sha256 or expect_size:
            bad = dest + ".bad"
            log.warn(t("net.cache.bad", nome=name,
                       arquivo=os.path.basename(bad)))
            try:
                if os.path.exists(bad):
                    os.remove(bad)
                os.replace(dest, bad)
            except OSError:
                pass
        else:
            log.ok(t("net.cache.using", nome=name, bytes=f"{have.size:,}"))
            return have

    tmp = dest + ".part"
    log.info(t("net.downloading", nome=name))
    log.cmd(f"GET {url}")
    md5, sha = hashlib.md5(), hashlib.sha256()
    done = 0
    started = time.time()

    try:
        with _open(url, timeout=90) as resp:
            total = int(resp.headers.get("Content-Length") or -1)
            with open(tmp, "wb") as out:
                while True:
                    if cancel and cancel():
                        raise Cancelled()
                    chunk = resp.read(256 << 10)
                    if not chunk:
                        break
                    out.write(chunk)
                    md5.update(chunk)
                    sha.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except Cancelled:
        _quiet_remove(tmp)
        raise
    except Exception as exc:
        _quiet_remove(tmp)
        raise _friendly(url, exc)

    got = Digests(md5.hexdigest(), sha.hexdigest(), done)
    secs = max(time.time() - started, 0.001)
    log.info(t("net.speed", nome=name, bytes=f"{done:,}", segundos=f"{secs:.1f}",
               taxa=f"{done / secs / 1e6:.1f}"))

    if expect_size is not None and got.size != expect_size:
        _quiet_remove(tmp)
        raise InstallerError(
            t("net.err.size.title", nome=name),
            t("net.err.size.body", esperado=expect_size, obtido=got.size,
              url=url))
    if expect_md5 and got.md5.lower() != expect_md5.lower():
        _quiet_remove(tmp)
        raise InstallerError(
            t("net.err.md5.title", nome=name),
            t("net.err.digest.body", esperado=expect_md5, obtido=got.md5,
              url=url))
    if expect_sha256 and got.sha256.lower() != expect_sha256.lower():
        _quiet_remove(tmp)
        raise InstallerError(
            t("net.err.sha.title", nome=name),
            t("net.err.digest.body", esperado=expect_sha256, obtido=got.sha256,
              url=url))

    os.replace(tmp, dest)
    log.ok(t("net.downloaded", nome=name))
    log.info(f"    md5    {got.md5}")
    log.info(f"    sha256 {got.sha256}")
    return got


def _quiet_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
