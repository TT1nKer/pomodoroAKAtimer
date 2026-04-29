use super::{Backend, Track};
use std::process::Command;

// macOS backend via the `nowplaying-cli` userspace helper.
//
// install: brew install nowplaying-cli
// project: https://github.com/kirtan-shah/nowplaying-cli
//
// rationale: apple's MediaRemote is a private framework. binding it
// directly from rust requires dlopen + objc gymnastics that's fragile
// across macOS versions. nowplaying-cli already does that work — we
// shell out to it the same way the linux python script shells out to
// playerctl. on linux the rust backend uses libdbus directly because
// d-bus has a stable, public api; mediaremote does not.

pub struct MacOsBackend;

fn npc(args: &[&str]) -> Option<String> {
    let out = Command::new("nowplaying-cli").args(args).output().ok()?;
    if !out.status.success() { return None; }
    let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if s.is_empty() || s == "null" { None } else { Some(s) }
}

impl Backend for MacOsBackend {
    fn now(&self) -> Track {
        let title  = npc(&["get", "title"]).unwrap_or_default();
        let artist = npc(&["get", "artist"]).unwrap_or_default();
        let album  = npc(&["get", "album"]).unwrap_or_default();
        let status = match npc(&["get", "playbackRate"]).as_deref() {
            Some("0") | Some("0.0") => "paused",
            Some(_)                 => "playing",
            None if title.is_empty() => "stopped",
            None                     => "playing",
        }.to_string();
        Track { player: String::new(), status, title, artist, album, art: String::new() }
    }

    fn play_pause(&self) { let _ = npc(&["togglePlayPause"]); }
    fn next(&self)       { let _ = npc(&["next"]); }
    fn previous(&self)   { let _ = npc(&["previous"]); }
}
