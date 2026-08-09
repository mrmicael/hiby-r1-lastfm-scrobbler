# Prebuilt device programs

The two programs that run **on the R1**, already cross-compiled for its CPU
(MIPS32 little-endian, statically linked, no libc on the device required).

| file | what it does |
|---|---|
| `r1collect` | reads the player's SQLite history and the Tidal track id; never writes |
| `r1send` | assembles and signs the Last.fm batch, and writes the card's CSV |
| `r1net` | the resident network helper: holds one TLS connection open so nothing has to be created mid-playback |

`r1net` is the odd one out. It exists because the R1 froze whenever the
scrobbler went to the network while Tidal was playing, and what every attempt
had in common was *creating* something at that moment — a fork, an exec, a
1.6 MB binary mapped in, a socket, a TLS handshake. It starts at boot, when
there are 22 MB free, does all of that once, and then sits on a fifo.

Measured on a real R1: **784 KB resident idle, 876 KB after the first request,
and still 876 KB after the fourth.** Requests cost nothing after the first.
`curl`, which it replaces for this path, is 1,643,940 bytes on disk and peaked
at 896 KB of *fresh* allocation on every single invocation.

Wiring it into the daemon produced three regressions in a row on a real
device: the announcement firing every 15 seconds, the announcement never
firing again after one transient failure, and duplicate entries in the queue.
So it is connected only behind a test that runs a whole listening cycle
**twice** — once through `curl`, once through the helper — and requires the
two queues to come out identical. That test is section 15 of
[`t_daemon.py`](../../testes/t_daemon.py), and it needs
[`servidor_falso.py`](../../testes/servidor_falso.py): a local HTTPS server
that generates its own certificate, so the helper's TLS validation is
exercised rather than switched off.

## Why they are here

Compiling them needs Zig, and on Windows that needs WSL — which turns
*"download it and install"* into *"first install a Linux distribution"* for
someone who just wants to scrobble. So they ship built.

**Nothing here is trusted blindly.** Whatever the program is about to push to
your device — these files or one you compiled — goes through the same ELF
check first: 32-bit, little-endian, EM_MIPS, statically linked, and the R1's
own `e_flags`. A file that does not pass never reaches the device.

If you compile your own, yours wins: the program looks in its work directory
first and only falls back to this folder.

## Building them yourself

The sources are two files, right next to this folder:
[`collector.c`](../collector.c) and [`r1send.c`](../r1send.c). Click **Build**
in the program, or do it by hand with [Zig](https://ziglang.org/download/):

```sh
zig cc -target mipsel-linux-musleabihf -Os -static -Wall -Wextra \
    -o r1collect ../collector.c
zig cc -target mipsel-linux-musleabihf -Os -static -Wall -Wextra \
    -o r1send ../r1send.c
```

`r1net` is not in that list because it needs mbedTLS. It has a script of its
own, [`build_r1net.sh`](../build_r1net.sh), which fetches the library and
builds it — a few minutes, and it needs the network, which is why it is not
behind the same button as the other two.

## SHA256 of the files in this commit

```
66d34da103db1b658c7713ca0032536805ba6c29f99bbb8807774f796538cb21  r1collect
b4ddb81cd5221230b14f30d90f0dffb6ab715420a82d1163fa3afd8cbaf10521  r1send
45fb9d9ee6f654eee01a8374ab32dcfe2fd22ecbf800fdba9880e95f6081bf6b  r1net
```

Built with Zig 0.16.0. Note that a rebuild will not necessarily match these
digests byte for byte — a different Zig version changes the output — so treat
them as a record of what this commit shipped, not as a reproducibility claim.
