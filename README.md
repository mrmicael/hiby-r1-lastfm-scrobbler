# Last.fm scrobbler for the HiBy R1

*[Leia em português](README.pt-BR.md)*

The R1 has no scrobbling. This puts a tiny collector inside the player that
writes down what you listen to — offline, on a plane, in a car — and sends it
all to Last.fm afterwards. If the R1's Wi-Fi happens to be on, it sends by
itself, with no PC in the loop.

Works on the **plain HiBy R1** (Ingenic X1600, MIPS32 little-endian, stock
firmware with ADB). No root, no firmware modification, and it never writes to
the player's database.

```bash
python r1lastfm.py
```

<p align="center">
  <img src="docs/janela-en.png" width="800"
       alt="The program's window: an explanation of how it works, and the card where you paste your Last.fm API key">
</p>

One window, six cards, top to bottom. Nothing is hidden in menus, and every
card says what it is about to do before it does it.

<p align="center">
  <img src="docs/janela-aparelho.png" width="800"
       alt="The device card: collector installed and running, 57 plays recorded, with the polling intervals">
</p>

The interface is in **English and Portuguese**, English by default, switchable
from the bottom-right corner of the window at any time.

<p align="center">
  <img src="docs/janela-pt.png" width="620"
       alt="The same window in Portuguese">
</p>

---

## What it does

* **Scrobbles Tidal too.** Streamed tracks never enter the player's local
  database, which is why most R1 scrobblers cannot see them at all. This one
  reads the Tidal track id the player leaves behind and asks Tidal's own API
  for the details, using the token already on the device.
* **Records offline.** You can spend a whole trip with no network: what played
  stays on the device and goes out when there is a connection.
* **Sends over Wi-Fi by itself.** Every twelve minutes the R1 checks whether a
  route out already exists. If it does, it sends. It **never switches the radio
  on by itself** — that stays your decision.
* **Sends over the cable too.** For people who never use the device's Wi-Fi:
  plug in, click send, done. Both paths coexist without duplicating anything.
* **“Now playing”, live.** The track you are playing shows up pulsing on your
  profile, if you want it.
* **Applies Last.fm's own rules** for what counts: half the track, or four
  minutes. A track you skipped halfway does not go.
* **Sends within ~30 seconds** of a track ending, not on a twelve-minute
  timer.
* **Writes a log and a spreadsheet to the memory card**, at
  `<card>/r1lastfm/`: `r1lastfm.log` and `scrobbles.csv`. Pull the card, open
  the CSV in a spreadsheet — no ADB, no this program, nothing.

## What it costs in battery

Measured on the device, not estimated:

| | cost |
|---|---|
| collector, idle | 1 ms of CPU per minute — 0.0017% of the time, **zero child processes** |
| collector, playing | one cycle every 15 s, same 1 ms per cycle |
| memory | 880 kB RSS |
| one Wi-Fi send | ~0.1% of the battery |
| “now playing” | 10 ms per detection; 2.4 s of CPU per **hour** |

What actually costs is having Wi-Fi on — the radio draws 50-150 mW against the
~260 mW of the device playing, which takes 20-40% off the battery life. That
bill belongs to Wi-Fi, not to this program: with the radio off, the collector's
cost is indistinguishable from zero.

## Step by step

### 0. What you need

| | |
|---|---|
| **Python 3.9+ with Tkinter** | standard library only; nothing to `pip install` |
| **adb** (Android Platform Tools) | how the program talks to the R1 |
| **WSL + Zig** | *only* for automatic Wi-Fi sending. The program downloads and installs Zig itself, verifying the SHA256 published by ziglang.org |

Without WSL/Zig the program is still useful: it collects, and sends over the
cable.

<details>
<summary><b>Installing adb</b></summary>

Download the Android Platform Tools for your system:
<https://developer.android.com/tools/releases/platform-tools>

* **Windows** — unzip it into `C:\platform-tools`. That is one of the places
  this program looks, so nothing else is needed.
* **macOS** — `brew install android-platform-tools`.
* **Linux** — `sudo apt install adb` (or your distribution's equivalent).

Check it with `python r1lastfm.py --check`.
</details>

<details>
<summary><b>Installing WSL (Windows, optional)</b></summary>

Only needed for Wi-Fi sending and “now playing”. In a PowerShell running as
administrator:

```powershell
wsl --install -d Ubuntu
```

Restart, then open Ubuntu once so it can finish setting itself up. You do not
need to install Zig — the program does that when you ask it to build.
</details>

### 1. Register your own Last.fm API key

Go to <https://www.last.fm/api/account/create> (the program has a button that
opens it). Fill in a name — something like *my R1 scrobbler* — and a
description. Everything else can stay empty. Submit, and copy the two values it
shows you: **API key** and **Shared secret**.

Paste both into card 1 and click *Save*.

> **Why your own key, and not one shipped with the program?** A shared secret
> published in a public repository is not a secret. Anyone could impersonate
> the application, and Last.fm would revoke it the moment they noticed —
> breaking it for everybody. Registering takes a minute and it is yours.

The key is stored on your computer only, in `config.json`. It is not your
password, and this program never sees your password at any point.

### 2. Authorise your account

Click *Authorise in the browser* in card 2. A page on Last.fm itself opens,
where you approve the access. Come back and click *I authorised it — finish*.

What comes back is a **session key**, not your password. You can revoke it at
any time at *last.fm → Settings → Applications*.

### 3. Connect the R1 and install the collector

On the device: **System → USB working mode → Device**. Then plug in the cable.

> ADB and USB-DAC share the same USB controller and are mutually exclusive: in
> DAC mode `adbd` does not even start, and the device list is empty exactly the
> way it is with a bad cable. Also check that the cable carries data — many
> only charge.

In card 3, click **Build** and then **Install / update**. Building takes a
minute or two the first time (the program downloads Zig if it needs to).

### 4. Reboot the R1

The collector is added to `/usr/data/init.sh` so it comes up with the player at
every boot. Reboot once and check card 3 — it should say *“Starts together with
the player.”*

At this point everything already works over the cable. **If you never want to
use Wi-Fi, you are done**: listen to music, plug in when you feel like it, click
*Fetch the queue* and *Send to Last.fm*.

### 5. (Optional) Automatic Wi-Fi sending

In card 4, in this order:

1. **Build curl** — 20 to 30 minutes, once per machine. It downloads the curl
   and Mbed-TLS sources from both projects' official sites and cross-compiles
   them for the R1's MIPS, on your computer.
2. **Download certificates** — the root bundle published by the curl project.
   Without it the device cannot verify who it is talking to.
3. **Enable Wi-Fi sending** — this puts the session key and the two programs on
   the device.
4. **Send now (test)** — proves it works without waiting twelve minutes.

Tick *Show “now playing” on my profile* if you want live scrobbling. It applies
immediately, no reinstall needed.

### Checking without opening the window

```bash
python r1lastfm.py --check
```

And to see everything it *would* do, without touching the device:

```bash
python r1lastfm.py --dry-run
```

`--lang en` / `--lang pt` forces a language for one run without changing your
preference.

## How it works inside

The R1 keeps an SQLite database at `/usr/data/usrlocal_media.db` with a
`HISTORY_TABLE`. It says **what** played and **in what order**, but records the
time of nothing — and the time is what Last.fm needs.

So the collector (`collector.c`, a hand-written SQLite reader, ~770 lines, no
libsqlite) looks at the database now and then and writes down the **device's
clock** at the moment each new row appears. The gap between two rows is how long
you heard the first one. Track duration is not in the database either: it is
computed from `size * 8 / bit_rate`, which matched the real length to within
half a second in testing.

Details that only turn up by working on the real device, and that are documented
in the code's comments:

* the player writes the history row **when the track ends**, not when it starts
  — measured at 194 s on a 3:14 track;
* every TEXT value in the database carries a trailing NUL byte (the player
  writes C strings);
* the card's `most_played.db` is corrupt out of the factory (one row mixes one
  track's name with another's path); only its mtime is used, never its contents;
* the database is opened **read-only, and on a copy** — the player never sees
  this program.

Sending from inside the device is done by `r1send.c`, which assembles and signs
the batch (MD5 over the sorted parameters plus the secret, as the Last.fm API
requires) and calls a static `curl`. The daemon (`r1scrobbled.sh`) is busybox
ash and sleeps on a `read -t` over a fifo, which costs 34× less than calling
`sleep` — that is why it spawns no processes at all while waiting.

## Where things live

**On this computer**, in `%LOCALAPPDATA%\R1LastFm` (Windows),
`~/Library/Application Support/R1LastFm` (macOS) or `~/.local/share/r1-lastfm`
(Linux):

* `config.json` — your API key, the Last.fm session key, and your language;
* `registros/` — the full log of every session, with the exact commands, so any
  step can be redone by hand;
* `trabalho/` — the compiled binaries.

**On the device**, in `/usr/data/scrobble`: the queue, the list of what was
already sent, and (if you enable Wi-Fi sending) the session key. They live there
on purpose — using the program from another computer then re-sends nothing and
loses nothing.

## Security, without decoration

* The program **never sees your password**. Authorisation happens on a Last.fm
  page; what comes back is a session key, revocable at any time at
  *last.fm → Settings → Applications*.
* If you enable automatic sending, that key is **written to the device**, at
  `/usr/data/scrobble/sk` with mode 600. It does not give access to your
  password, but **anyone with ADB access to the device can read it**. If that
  bothers you, use cable sending only: it works just as well, and nothing leaves
  the PC.
* Without the certificate bundle on the device, the daemon **refuses to send**
  rather than handing over the key without checking who is on the other end.
* No binary is downloaded ready-made. `curl` is compiled on your machine from
  the official curl and Mbed-TLS sources, and whatever comes out still goes
  through an ELF check before reaching the device.

## Uninstalling

The **Remove** button, in card 3, takes everything out: the programs, the
`init.sh` block, and (if you say so) the queue. Nothing outside
`/usr/data/scrobble` and `/usr/data/init.sh` is ever touched.

## It did not work?

The session log has the exact command for every step — it is the first place to
look, and it is designed so you can redo it by hand line by line. Some common
cases:

* **“nothing shows up on Last.fm after a reboot”** — check in card 3 that it
  says *Starts together with the player*. If your `init.sh` has an `exit` before
  the scrobbler block, it never runs; the program inserts the block **before**
  the first `exit` for exactly this reason.
* **“automatic sending never sends”** — the R1 does not turn Wi-Fi on by
  itself. Turn it on and wait up to twelve minutes, or use *Send now (test)*.
* **“old scrobbles do not go up”** — Last.fm refuses timestamps older than 14
  days. Nothing to be done.

## Running the tests

```bash
python testes/t_scrobble_all.py
```

Twelve modules: the SQLite reader in C against real SQLite, the daemon running
under busybox ash, queue reconstruction, signing, automatic sending, live “now
playing”, the `init.sh` edits, the device API against a fake adb, the ELF check,
the window itself, and the translation catalogue.

Tests that talk to the real Last.fm API are skipped unless you provide your own
key:

```bash
LASTFM_API_KEY=... LASTFM_API_SECRET=... python testes/t_scrobble_all.py
```

## Translating

Every user-visible string lives in [`r1lastfm/textos.py`](r1lastfm/textos.py),
one key per message, one entry per language. To add a language, add its code to
`IDIOMAS` in [`r1lastfm/idioma.py`](r1lastfm/idioma.py) and a matching entry to
every key. Then run:

```bash
python testes/t_idioma.py
```

It walks the whole source, collects every key that is asked for, and tells you
exactly which ones you missed — including any whose `{placeholders}` do not
match the English original.

## Credits

Written with [Claude Code](https://claude.com/claude-code) (Anthropic).

The SQLite file format, the R1's `HISTORY_TABLE` behaviour and the battery
numbers above were all worked out on the device, by measuring — not estimating.

MIT licence, in [LICENSE](LICENSE).
