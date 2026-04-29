use super::{Backend, Track};

// macOS backend stub.
//
// implement by binding to apple's private MediaRemote framework via objc.
// references:
//   https://github.com/PrivateFrank/MediaRemote
//   https://github.com/ungive/media_control
//
// uncomment the [target.macos] block in Cargo.toml when adding objc/core-foundation deps.

pub struct MacOsBackend;

impl Backend for MacOsBackend {
    fn now(&self) -> Track {
        Track {
            status: "stopped".into(),
            player: "macos:unimplemented".into(),
            ..Default::default()
        }
    }
}
