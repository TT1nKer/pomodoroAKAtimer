# timer-bridge (rust)

cross-platform rewrite of `bridge.py`. wire-compatible with the python
script — same endpoints, same json shape — so the timer ui needs no change.

## status

| platform | backend | works |
|----------|---------|-------|
| linux    | mpris (d-bus) | yes — covers spotify desktop, netease cloud, mpd, browser players |
| macos    | mediaremote   | stub — returns `status: stopped` |
| windows  | smtc          | stub — returns `status: stopped` |

the macos and windows backends compile but always report stopped. they
exist so contributors can fill them in without touching the http server
or the timer ui. see `src/backend/macos.rs` and `windows.rs` for the
crate refs and api sketches.

## build

```sh
# install rust if you don't have it: https://rustup.rs
cargo build --release
./target/release/timer-bridge
```

then in the timer settings: enable music bridge, url `http://localhost:7777`.

## why rewrite the python one

| | python | rust |
|---|---|---|
| install | python + playerctl | one binary |
| platforms | linux only | linux now, macos/windows stubs |
| size | ~3 kb script | ~2 mb stripped binary |
| dependencies at runtime | python interpreter, playerctl cli | none |

the python script stays the canonical "scratch your own itch on linux"
form. the rust binary is the path toward distributing precompiled
binaries on the github releases page (and eventually a proper installer).

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
2. uncomment the matching block in `Cargo.toml`
3. wire it in `src/backend/mod.rs::default_backend()`

`Backend` only requires `now()`; control methods default to no-ops, so a
read-only backend is fine for a first pass.
