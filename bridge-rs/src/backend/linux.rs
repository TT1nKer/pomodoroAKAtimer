use super::{Backend, Track};
use mpris::{PlaybackStatus, Player, PlayerFinder};

pub struct LinuxBackend;

impl LinuxBackend {
    fn active(&self) -> Option<Player> {
        PlayerFinder::new().ok()?.find_active().ok()
    }
}

impl Backend for LinuxBackend {
    fn now(&self) -> Track {
        let Some(p) = self.active() else { return Track::stopped() };

        let status = p.get_playback_status().map(|s| match s {
            PlaybackStatus::Playing => "playing",
            PlaybackStatus::Paused  => "paused",
            PlaybackStatus::Stopped => "stopped",
        }).unwrap_or("stopped").to_string();

        let meta = p.get_metadata().ok();
        let (title, artist, album, art) = match meta {
            Some(m) => (
                m.title().unwrap_or("").to_string(),
                m.artists().map(|v| v.join(", ")).unwrap_or_default(),
                m.album_name().unwrap_or("").to_string(),
                m.art_url().map(|u| u.to_string()).unwrap_or_default(),
            ),
            None => Default::default(),
        };

        Track {
            player: p.identity().to_string(),
            status, title, artist, album, art,
        }
    }

    fn play_pause(&self) { if let Some(p) = self.active() { let _ = p.play_pause(); } }
    fn next(&self)       { if let Some(p) = self.active() { let _ = p.next(); } }
    fn previous(&self)   { if let Some(p) = self.active() { let _ = p.previous(); } }
}
