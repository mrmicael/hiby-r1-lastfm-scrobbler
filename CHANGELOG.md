# Changes since the last release

## Device version 20 — the Tidal crash, measured instead of guessed

Versions 18 and 19 both moved `curl` around inside the Tidal path, and neither
worked. This one starts from measurements taken on the device while it was
playing.

**What is actually true on an R1:**

| | idle | playing |
|---|---|---|
| free memory | 22 MB | **1.5 MB** |
| largest contiguous block | 16 MB (order 12) | **512 KB (order 7)** |

And the R1's kernel is built **without memory compaction** — there is no
`/proc/sys/vm/compact_memory` and no compaction counters in `/proc/vmstat`. So
that collapse never recovers until the audio stops. It is a one-way door.

Into that, the daemon was running `curl`, which is 1,643,940 bytes against the
collector's 77,940. The player was not dying of running out of memory —
`MemAvailable` stays around 10 MB. It was dying of not getting the *piece* it
asked for.

And when it dies, `/usr/bin/hiby_player.sh` — the firmware's supervisor —
restarts it, and after five deaths in a row it calls `reboot`. That is what a
"freeze" was.

Playing from the card never hit this, because there the player is far smaller.
On Tidal it holds 20 MB resident, 32 threads and 14 open sockets.

**The rule now:** while Tidal is playing, the daemon only writes text. No
lookup, no sending, no spreadsheet — the track id and its start and end times
go into a small pending file, which costs no process at all. Everything that
needs the network waits for the silence and goes out on the first cycle after
it. Nothing on the card path was touched.

Two consequences worth knowing:

- **Tidal loses "now playing."** Announcing needs two network round trips, and
  both would have to happen while the audio is playing. Announcing afterwards
  would not be announcing anything. The scrobble itself is unaffected — it is
  written to the queue and sent in full. Local files keep their "now playing".
- **Repeats are now detected afterwards**, from the total elapsed time and the
  duration, instead of during playback. This is both simpler and more correct:
  it no longer needs the duration — and therefore the network — while the track
  is running.

**When a Tidal scrobble reaches Last.fm:** nothing goes out while you keep
playing — a track change does not count, because the audio never stops. Once
you do stop, the daemon resolves one pending track per loop and each resolved
track pulls the send in to 45 seconds. The loop stays at its fast pace while
anything is pending, so a twenty-track session drains in about five minutes
instead of a quarter of an hour. The timestamps are the real ones: every track
carries the moment it started and ended, so a late send does not shift anything
on your profile.

Tracks shorter than 25 seconds are dropped before they reach the pending file.
They could never pass the 90% rule anyway, and skipping through a list used to
spend one network lookup on each one.

---

## Device version 19 — two curls at once was the rest of the Tidal crash

> *"it also crashes the same way in the podcast app"*

Version 18 moved the Tidal metadata lookup off the instant of the track change.
It was not enough, and this is why: the moment that lookup came back, the very
next line sent the "now playing" to Last.fm. Two copies of `curl` — a 1.6 MB
static program each, plus its own TLS buffers — alive at the same moment, on a
device whose free memory is usually between 1.5 and 2.5 MB.

Playing from the card never did this. There is no Tidal lookup there, so there
was only ever one `curl`. That is the whole difference between the path that
crashed and the path that stopped crashing, and it is why fixing the card did
nothing for Tidal.

The two are a full cycle apart now, and the announcement checks the free memory
for itself before it runs — if it is short, it waits another cycle instead of
insisting. A missed "now playing" costs nothing: the scrobble is written to the
queue separately.

The pending announcement is dropped if the track changes or the audio stops
before it goes out, so a delayed announcement can never put the wrong track on
the profile.

Nothing outside `olhar_tidal` was touched.

---

## Device version 18 — the Tidal lookup ran at the instant of the track change

Asking Tidal's servers for a track's title meant running `curl` exactly when
the player was allocating buffers for the new track — a memory spike landing on
the tightest moment there is. It waits one cycle now, and holds off if memory
is still short when it tries.

---

## Device version 17 — skipping quickly counted as listening

> *"those two, Super Duper and Enemy: I didn't listen to them, I skipped them,
> and they counted anyway"*

Five tracks about a minute apart, all scrobbled.

This came from the version 13 fix. When several rows land in a single look at
the player's database — which is exactly what fast skipping produces — they
were marked as tracks played while the collector was not running. That
treatment reconstructs their times **backwards from each track's own length**,
which credits every one of them in full.

The real window is shared out between them now. Three rows arriving in 45
seconds means nobody heard more than fifteen, and the 90% rule throws all three
out.

Nothing was added to the moment a track changes.

---

## Device version 16 — a skip could disguise itself as an ending

> *"see that I Heard It Through the Grapevine? I skipped it and it counted
> anyway"*

Version 15 started telling a track that **finished** apart from one that was
**skipped**, by watching the audio: skipping leaves the audio playing right up
to the skip, while a track that ends stops the audio first.

That signal is good but not infallible. Between one track and the next there is
a moment of silence, and when you skip, the collector can look exactly then —
so the skip disguises itself as an ending. The bar for that case was **half**
the track, which let a track skipped past its midpoint go up as listened.

It is **80%** now. That covers a track length that reads long because of cover
art and tags, which is what the rule exists for, and comes nowhere near
covering a skip.

Nothing was added to the moment a track changes: this is one comparison inside
a program that was already running.

---

## Device version 15 — two things reported as "it isn't counting my tracks"

### A track that reached its own end now counts

> *"it doesn't count songs that weren't 100% listened to — like only 3:21 of
> 3:27, when the rest is just silence"*

Track length is worked out from `size × 8 / bitrate`, which comes out long on a
file carrying cover art and tags. Silence at the end shortens the measurement.
Together they could reject a track played all the way through.

The collector now tells **finishing** apart from **skipping** without doing
that arithmetic at all: skipping leaves the audio playing right up to the skip,
so the audio device is still open when the next track's row arrives. A track
that ends on its own stops the audio first. That difference is observable, and
it does not care whether the stored length is honest.

Opening a track and walking away still does not count — that also ends with the
audio stopped, so it is capped at having heard at least half.

### Scrobbles no longer get stuck while you skip around

The other half of the report was mine. In version 14 each track change pushed
the send back, so someone skipping constantly never sent anything. The tracks
were measured and approved and simply sat in the queue — from outside, that is
indistinguishable from not being counted.

There is a ceiling now: the send is still deferred to keep `curl` away from
track changes, but never by more than 150 seconds.

---

## Device version 14 — the collector was crashing the R1 on track changes

The device would freeze and reboot while skipping through tracks. Removing the
collector stopped it; putting it back brought it back. That reproduction is
what identified the cause, after a long stretch of wrong guesses — the memory
card, the firmware's memory fragmentation, a wedged kernel worker. None of
those were it.

At **every track change** the collector was doing all of this in the same
second the player was allocating buffers for the new track, on a device that
runs with about **1.7 MB free**:

| what it did | cost |
|---|---|
| copied the player's whole database to `/tmp`, which is RAM | **624 kB** |
| ran the collector on the copy | a process |
| rewrote the card's spreadsheet | another process |
| fired the send, which executes `curl` | **1.6 MB**, larger than the free memory |

Four changes, each aimed at one of those:

* **The database is read in place.** The copy existed to guard against reading
  while the player writes; the "read failed, try again next cycle" path
  already existed and was already tested, so it becomes the primary path
  instead of the fallback.
* **The send is rescheduled, not fired.** Each track change pushes the clock
  forward again, so skipping five tracks in a row runs `curl` zero times — it
  goes out once things settle, sending everything together.
* **The spreadsheet is rewritten at most once a minute** instead of once per
  track.
* **The read waits a few seconds** after the database changes, so the work
  lands after the player has settled rather than on top of it.

Scrobbles now reach your profile about half a minute later than before. That
is cheap next to the device restarting mid-song.

**This is not promised as a cure.** It removes the four costs that could be
named and measured. If the freezing survives it, the changes can be disabled
one at a time against the same reproduction.

---

## Device version 13 — the first track of an album was being lost

> *"any time I start an album, the first song never gets scrobbled. It's
> always the following song that gets logged. It does show up on scrobbling
> now."*

Reported with screenshots, and reproduced exactly.

The collector drops to a slow rhythm when the device is idle, so starting an
album could put **two rows in the player's database before its first look**.
Both then carried the same timestamp — the moment of that look — so the gap
between them was zero, and everything but the last row was thrown away as
"heard nothing". The now-playing update does not depend on any of that, which
is why the track appeared on the profile as *scrobbling now* and then never
went up.

Rows that were not seen starting are the same situation as tracks played while
the collector was not running, and there is already a marker for that: the
times are reconstructed backwards from each track's own duration. Only the
last row of a harvest is the one actually playing, and that one is measured as
usual.

The old behaviour is now pinned by a test, so it cannot come back unnoticed.

### An empty mount point is not a memory card

Found while chasing something else: the card slot's mount point still exists
when there is no card in it — it is an ordinary writable directory in internal
memory, and it passed the write test like any other. The collector announced
*"log and spreadsheet on the card"* with an empty slot and wrote both to
internal memory, where they would become invisible the moment a card was
inserted and mounted over them. It now requires a filesystem to actually be
mounted there.

---

Three device versions in one drop — **10** (the stricter listening rule),
**11** (the measurement rewrite) and **12** (finding the player's database) —
plus installer fixes that need no device update. Update the device from
**card 3**; the installer fixes come with the program itself.

---

## Device version 12 — the player's database is not always where it was

> *"I have installed version 11 and the Python app says it is running. I have
> been playing some music, but 0 plays have been collected. I think I see the
> problem: I have enabled the setting to save usrlocal_media.db to the SD
> card, so the one in /usr/data/ is not updated."*

That is exactly it, and the collector was at fault: it read one hardcoded
path. The player has a setting on its own screen — `tf_music_db_enable` —
that moves its music database to the memory card, and from then on the copy
in internal memory is never written again. Anyone with that turned on got a
program that said "running" and collected nothing, with nothing on screen
explaining why.

Both paths are inside `/usr/bin/hiby_player` itself:

```
/data/usrlocal_media.db                   setting off
/data/mnt/sd_0/.temp/usrlocal_media.db    setting on
```

The collector now asks the most direct question there is: **which database
file does the player have open?** That is read from its open file descriptors,
so it is not a guess, a heuristic or a timestamp — it is the file in use,
right now, by the process using it.

The obvious alternative — read the setting — was raised and is worth
recording, because the answer is not what it looks like.
`tf_music_db_enable` in `/usr/resource/config.json` only enables the *menu
entry*; it does not hold the value. That file is the only `config.json` on the
device, it lives on the read-only squashfs, and on a real R1 it says `1` while
the player is using the internal database. The effective value is a single
byte inside `/usr/data/user.ini` — byte 2217 on two devices checked, `0` off
and `1` on, confirmed on both. But `user.ini` is a packed binary struct with
no keys and no header, so that offset holds only as long as the layout does:
one extra field in a future firmware and the check answers confidently and
wrongly, which is precisely the bug being fixed here.

Modification time is kept as a fallback, for the first install and for a
collector older than this. And when the player is not running at all — at
boot it starts after the collector — the previously recorded database is
kept rather than second-guessed, so a quiet night cannot fake a switch.

**Switching between them is the dangerous part.** The two databases number
their rows independently, so carrying the old marker across would either skip
everything or — much worse — dump the entire history into the queue as dozens
of false scrobbles at once. On a switch the marker restarts at the top of the
new database, and the log says so.

The device log now names the database in use on every start, and the window
says when it is on the card.

### Start times are read from the database, not from the clock

The database's modification time is the moment the player wrote the row —
that is, the moment the track actually started. The collector used to start
counting when it *noticed*, up to one polling interval later, and that time
vanished from the beginning of every track. Measured on a real device, a
single track change recovered **nine seconds**; the declared uncertainty
drops from 15s to 2s. If the timestamp does not make sense (a clock just set,
a card with a wrong date) the log says so and the old behaviour applies.

---

## Device version 11 — listening time is measured, not inferred

Two reports, one root cause.

> *"Right Now, Levitate and Morph each showed up on my profile twice — once as
> a scrobble and once as scrobbling now, at the same time."*

> *"Some songs I know I have played are not being logged. Other songs do get
> logged, but not all."*

Both came from the same shortcut: the time you had listened was taken from the
**gap between two rows** of the player's history. That gap is wall-clock time,
not music, and the two only agree when nobody pauses, nobody turns the player
on mid-track, and nothing is left open at the end of a session. When they
disagree, it is always the inference that is wrong — it counted silence as
music.

So the collector now **counts the seconds audio is actually coming out of the
device** and writes the total down. Everything below follows from that.

### Pausing no longer throws the track away

Pausing closed the audio device exactly like switching the player off, so the
track was closed on the spot with half a listen — below the minimum, and
discarded. Someone who pauses in the middle of a song and comes back has heard
the song.

The device tells the two apart, and this was measured on a real R1 with the
pause pressed by hand:

```
50s  pcm=1  rowid=261  arq=.../After Dark.flac    playing
50s  pcm=0  rowid=261  arq=.../After Dark.flac    PAUSED
29s  pcm=1  rowid=261  arq=.../After Dark.flac    resumed
```

The audio device closes; the **file does not**. And the history row never
changed — resuming writes nothing at all, which is why there was no other
signal to go on. So:

| audio | file open | meaning |
|---|---|---|
| out | yes | playing — count it |
| stopped | yes | paused — do not count, do not close |
| stopped | no | playback ended — close the track |

A pause only stops the clock. There is a 30-minute ceiling so a track cannot
stay open forever if you pause and walk away.

### A track already playing when the collector starts is no longer "backlog"

The collector woke up, found the row of the track playing *at that moment*,
called it "played while nobody was watching", gave it full credit and sent it
immediately. That is the duplicate on the profile: it really was playing.

A track playing right now is not the past. It is left out of the backlog and
counted from zero like any other. The part that had already played is lost —
better than inventing a whole listen.

### Restarting mid-track no longer abandons the rest of it

Resuming writes no history row, so a collector that started with music already
playing and the database fully recorded saw nothing to do — and nobody counted
the rest of the track. Seen on the device: a track played 39s, sat paused for
14 minutes, came back and played 82 more, and was filed with the 34s the
*previous* collector had measured.

It now adopts the track that is already playing and measures the remainder.
Measurements of the same track add up, so the two halves join.

### A crash no longer takes the measurement with it

This R1 reboots on its own — it did so four times while this version was being
written — and no cleanup handler runs during a crash. The count, which lived
only in the collector's memory, died with it: the track came out with no
measurement, and the arithmetic fell back to the clock. That is how a 293s
track that rebooted the device halfway still went up as fully played.

The measurement is now checkpointed to a small file every 30 seconds and turned
into a finished track on the next start. The queue is not used for this: it is
never pruned, and a line every 30 seconds of music would make it grow ten times
faster, forever.

### The measurement carries its own uncertainty

The audio state is sampled every so often, so each time it starts or stops the
exact moment is lost inside one sampling interval. Measured live: a 6-second
pause was counted as 15 by a collector looking every 15 seconds — the 9-second
difference is music that played and was not added.

That uncertainty is added up honestly (one interval per boundary, so a track
heard straight through has almost none and a track paused three times has more)
and sent along with the total. The 90% bar is judged with it, because charging
90% against a number known to be short would reject a track heard to the end.
It never lowers the bar by more than ten points: nothing counts with less than
80% of the track actually played.

### Smaller things in the same version

* **The last track of a session no longer waits twelve minutes.** Only a track
  change used to bring the send forward, so the last song of the evening — the
  one you are waiting to see appear — sat in the queue after the device had
  already gone quiet. Measured at 1.3s in tests.
* **A track that is still playing is no longer called `skipped`.** The card's
  spreadsheet has a new `playing` status, and the window says *"still playing —
  it goes up on its own when it ends"* instead of claiming you did not listen
  enough. Accusing the program's own user of skipping the song they are
  listening to right now is the kind of small lie that makes people think the
  thing is broken.
* **Trimming the queue now removes the measurements too.** They were being left
  behind, so the queue kept growing during its own cleanup.
* **Uninstalling removes the checkpoint file**, so a later install cannot
  recover a listen from months ago.

---

## Device version 10 — the strict listening rule, and removing rows

* **A track has to play almost to the end to count: 90% of it**, or four
  minutes, whichever comes first. Last.fm settles for half, which meant a track
  you walked away from went up as if you had listened to it — *"I skipped that
  track and it counted as if I had listened to the whole thing."*

  Half also had an extra rounding bug: `duration / 2` in integer arithmetic
  gives 62 for a 125s track, and 62 >= 62 passes — so 49.6% counted. The
  arithmetic now rounds up.

* **You can select rows in the queue and discard them.** Wanting one track off
  your profile no longer means wiping the whole queue. They are marked as
  already handled on the device, which is the same mechanism that keeps a sent
  track from going up twice. Nothing is deleted from the player's own history.

---

## Installer and window — no device update needed

* **"No writable memory card found" when the card was perfectly writable.**
  The check was looking for `scrobbles.csv`, so a card that simply had not been
  written to yet looked unwritable. It now writes and removes a temporary file
  at the root of the card. (The first attempt at this fix created a directory
  during what is supposed to be a read-only status query — that is fixed too.)

* **A curl that segfaulted on every request.** `--disable-threaded-resolver`
  was in the build recipe as a correctness fix for static musl builds. The
  reasoning was sound and the result was worse: the resulting binary died with
  signal 11 on every request, so turning on Wi-Fi sending broke sending. The
  flag is gone, with a comment explaining why it must not come back, and the
  installer now **proves the binary runs on the device** before it replaces the
  working one — it goes up under a temporary name and is only promoted after it
  answers.

---

## Under the hood

* Both implementations of the counting rule — the C on the device and the
  Python on the PC — are compared against each other case by case in the tests.
  They have to agree line for line: the card's spreadsheet comes from one and
  what goes to Last.fm passes through the other, and a previous version sent a
  track its own CSV called `skipped`.
* The threshold arithmetic used to be written twice in the C, and the two
  copies had already drifted apart once. It is one function now.
* New tests, all of them running the real collector under the device's own
  shell: pausing mid-track, starting with music already playing, restarting
  mid-track, a crash (`SIGKILL`, no chance to say goodbye) and its recovery,
  and the `awk` that trims the queue — which is sent to the device as *text*,
  so an error in it raises no exception on the PC and would only be visible to
  someone opening the file on the player.
