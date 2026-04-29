# timer-bridge (rust)

cross-platform rewrite of `bridge.py`. wire-compatible with the python
script — same endpoints, same json shape — so the timer ui needs no change.

## status

| platform | backend | how |
|----------|---------|-----|
| linux    | mpris (d-bus) | `mpris` crate, libdbus dynamic link. covers spotify desktop, netease cloud, mpd, browser players. ~680 kb. |
| macos    | mediaremote (via [nowplaying-cli](https://github.com/kirtan-shah/nowplaying-cli)) | shells out — mediaremote is a private apple framework, the cli already does the objc binding. install: `brew install nowplaying-cli` |
| windows  | smtc | `windows` crate, `Media_Control` feature. uses `GlobalSystemMediaTransportControlsSessionManager` — covers spotify, groove, edge / chrome / firefox players. |

## download

precompiled binaries for each release: <https://github.com/TT1nKer/pomodoroAKAtimer/releases>

| platform | asset |
|----------|-------|
| linux x86_64 | `timer-bridge-linux-x86_64` |
| macos apple silicon | `timer-bridge-macos-aarch64` |
| windows x86_64 | `timer-bridge-windows-x86_64.exe` |

ci matrix builds them on tag push (see `.github/workflows/release.yml`).

## build from source

```sh
# install rust if you don't have it: https://rustup.rs
cargo build --release
./target/release/timer-bridge
```

then in the timer settings: enable music bridge, url `http://localhost:7777`.

linux build needs `libdbus-1-dev` + `pkg-config` at compile time
(runtime needs only `libdbus-1.so.3`, present on every desktop linux).

## why rewrite the python one

|                          | python              | rust                                   |
|--------------------------|---------------------|----------------------------------------|
| install                  | python + playerctl  | one binary                             |
| platforms                | linux only          | linux + macos + windows                |
| size                     | ~3 kb script        | ~680 kb stripped release binary        |
| runtime deps             | python, playerctl   | libdbus (linux), nowplaying-cli (mac), winrt (windows, builtin) |

the python script stays the canonical "scratch your own itch on linux"
form. the rust binary is what gets distributed via github releases.

## endpoints

```
GET  /now           -> { player, status, title, artist, album, art }
POST /play-pause    -> /now after toggle
POST /next          -> /now after skip
POST /previous      -> /now after skip back
```

CORS is open (`Access-Control-Allow-Origin: *`) and the server binds to
`127.0.0.1`, so it's only reachable from the local machine.

## adding a backend

1. write `src/backend/<os>.rs` with a struct implementing `Backend`
2. add the matching `[target.'cfg(target_os = "<os>")'.dependencies]` block in `Cargo.toml`
3. wire it in `src/backend/mod.rs::default_backend()`
4. add a job to `.github/workflows/release.yml`

`Backend` only requires `now()`; control methods default to no-ops, so a
read-only backend is fine for a first pass.
