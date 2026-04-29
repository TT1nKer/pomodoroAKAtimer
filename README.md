# timer

a minimalist pomodoro timer. single-file html, vue 3 bundled, runs offline.

```
index.html         # the entire app — open it in a browser
vue.global.prod.js # vue runtime (offline)
bridge.py          # optional linux-only python daemon for music integration
bridge-rs/         # optional cross-platform rust daemon (linux/macos/windows)
```

live: <https://tt1nker.github.io/pomodoroAKAtimer/>

## use

open `index.html` in a browser, or visit the live link above.
press `f` for fullscreen.

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

## music bridge (optional)

the timer can show what's playing on your desktop music player and let you
skip / pause from the timer ui. this requires a tiny local daemon because
browsers can't read mpris / mediaremote / smtc directly.

**recommended — precompiled binary** (linux / macos / windows):
download the matching binary from
[github releases](https://github.com/TT1nKer/pomodoroAKAtimer/releases),
chmod +x it, run. then in the timer: settings → music bridge → enable.

**alternative — python script** (linux only):
```sh
sudo pacman -S playerctl     # arch — adjust for your distro
python bridge.py             # in this folder; ctrl-c to stop
```

**alternative — build from source**: see [bridge-rs/README.md](bridge-rs/README.md).

works with anything that publishes mpris (linux), mediaremote (macos via
[nowplaying-cli](https://github.com/kirtan-shah/nowplaying-cli)), or smtc
(windows): spotify desktop, apple music, netease cloud, mpd, browser
players, etc.

**status indicator** in settings tells you whether the timer can reach the
daemon. if it goes red, the daemon isn't running.

## stats persistence

stats live in `localStorage` under origin `pomodoro.stats.v1`. the timer
file's path is part of that origin: if you move the html file, old stats
won't be visible from the new path. for a stable origin, serve the file
over http (anything works — `python -m http.server`, github pages, etc.).

## license

mit.
