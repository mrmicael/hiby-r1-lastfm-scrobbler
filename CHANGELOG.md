# Changes since the last release

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
