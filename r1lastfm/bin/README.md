# Prebuilt device programs

The two programs that run **on the R1**, already cross-compiled for its CPU
(MIPS32 little-endian, statically linked, no libc on the device required).

| file | what it does |
|---|---|
| `r1collect` | reads the player's SQLite history and the Tidal track id; never writes |
| `r1send` | assembles and signs the Last.fm batch, and writes the card's CSV |

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

## SHA256 of the files in this commit

```
13f9ebace833630013edcb5f3feebfc10f2d3912dcfc3bf0ce8837f0922c55e2  r1collect
4da5eb04eeb6286d6e39a238a3a2c65f0b6ee90d903072257b2db88d99c0b645  r1send
```

Built with Zig 0.16.0. Note that a rebuild will not necessarily match these
digests byte for byte — a different Zig version changes the output — so treat
them as a record of what this commit shipped, not as a reproducibility claim.
