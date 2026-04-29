# timer

a minimalist pomodoro timer. single-file html, vue 3 bundled, runs offline.

```
timer.html         # the entire app — open it in a browser
vue.global.prod.js # vue runtime (offline)
bridge.py          # optional, linux-only: exposes the desktop music player
```

## use

open `timer.html` in a browser. press `f` for fullscreen.

- `space` start / pause
- `n` next phase · `r` reset
- `e` edit time · `↑`/`↓` ±1m (`shift` ±5m) · scroll on digits = same
- `s` session · `,` settings · `f` fullscreen

## features

- custom session sequences (drag to reorder) + presets: classic / long / ultradian / sprint
- focus stats — daily / weekly / monthly / yearly + last-30-days chart
- end-of-phase alert at three intensities — gentle / strong / persistent
- wake-lock keeps the screen on while running
- dynamic progress favicon, "ends at hh:mm" eta
- fully offline — no network calls, no telemetry, no accounts

## music bridge (optional, linux only)

the timer can show what's playing on your desktop music player and let you
skip / pause from the timer ui. this requires a tiny local daemon because
browsers can't read mpris over d-bus directly.

**setup:**
```sh
sudo pacman -S playerctl     # arch — adjust for your distro
python bridge.py             # in this folder; ctrl-c to stop
```

then in the timer: settings → music bridge → enable.

works with anything that publishes mpris: spotify desktop, netease cloud,
mpd / mopidy, browser players (firefox, chrome), and others.

**status indicator** in settings tells you whether the timer can reach the
daemon. if it goes red, the daemon isn't running.

**not on linux?** the music feature is opt-in and the timer works fine
without it. equivalent bridges for macos (mediaremote) and windows (smtc)
are out of scope for the python script — prs welcome.

## stats persistence

stats live in `localStorage` under origin `pomodoro.stats.v1`. the timer
file's path is part of that origin: if you move the html file, old stats
won't be visible from the new path. for a stable origin, serve the file
over http (anything works — `python -m http.server`, github pages, etc.).

## license

mit.
