use super::{Backend, Track};
use windows::Media::Control::{
    GlobalSystemMediaTransportControlsSession as Session,
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
};

pub struct WindowsBackend;

impl WindowsBackend {
    fn session(&self) -> Option<Session> {
        let mgr = SessionManager::RequestAsync().ok()?.get().ok()?;
        mgr.GetCurrentSession().ok()
    }
}

impl Backend for WindowsBackend {
    fn now(&self) -> Track {
        let Some(s) = self.session() else { return Track::stopped() };

        let status = s.GetPlaybackInfo()
            .ok()
            .and_then(|i| i.PlaybackStatus().ok())
            .map(|st| match st {
                Status::Playing => "playing",
                Status::Paused  => "paused",
                _               => "stopped",
            })
            .unwrap_or("stopped")
            .to_string();

        let media = s.TryGetMediaPropertiesAsync().ok().and_then(|op| op.get().ok());
        let (title, artist, album) = match media {
            Some(m) => (
                m.Title().map(|h| h.to_string()).unwrap_or_default(),
                m.Artist().map(|h| h.to_string()).unwrap_or_default(),
                m.AlbumTitle().map(|h| h.to_string()).unwrap_or_default(),
            ),
            None => Default::default(),
        };
        let player = s.SourceAppUserModelId().map(|h| h.to_string()).unwrap_or_default();

        Track { player, status, title, artist, album, art: String::new() }
    }

    fn play_pause(&self) {
        if let Some(s) = self.session() {
            let _ = s.TryTogglePlayPauseAsync().and_then(|op| op.get());
        }
    }
    fn next(&self) {
        if let Some(s) = self.session() {
            let _ = s.TrySkipNextAsync().and_then(|op| op.get());
        }
    }
    fn previous(&self) {
        if let Some(s) = self.session() {
            let _ = s.TrySkipPreviousAsync().and_then(|op| op.get());
        }
    }
}
