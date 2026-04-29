use super::{Backend, Track};

// Windows backend stub.
//
// implement using `windows-rs`:
//   Windows::Media::Control::GlobalSystemMediaTransportControlsSessionManager
//
// rough sketch:
//   let mgr = GlobalSystemMediaTransportControlsSessionManager::RequestAsync()?.get()?;
//   let session = mgr.GetCurrentSession()?;
//   let info = session.GetPlaybackInfo()?;
//   let media = session.TryGetMediaPropertiesAsync()?.get()?;
//
// uncomment the [target.windows] block in Cargo.toml when adding the windows crate.

pub struct WindowsBackend;

impl Backend for WindowsBackend {
    fn now(&self) -> Track {
        Track {
            status: "stopped".into(),
            player: "windows:unimplemented".into(),
            ..Default::default()
        }
    }
}
