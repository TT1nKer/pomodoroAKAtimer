use serde::Serialize;

#[derive(Default, Serialize)]
pub struct Track {
    pub player: String,
    pub status: String,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub art: String,
}

impl Track {
    pub fn stopped() -> Self {
        Track { status: "stopped".into(), ..Default::default() }
    }
}

pub trait Backend: Send + Sync {
    fn now(&self) -> Track;
    fn play_pause(&self) {}
    fn next(&self) {}
    fn previous(&self) {}
}

#[cfg(target_os = "linux")]
mod linux;
#[cfg(target_os = "macos")]
mod macos;
#[cfg(target_os = "windows")]
mod windows;

pub fn default_backend() -> Box<dyn Backend> {
    #[cfg(target_os = "linux")]    { Box::new(linux::LinuxBackend) }
    #[cfg(target_os = "macos")]    { Box::new(macos::MacOsBackend) }
    #[cfg(target_os = "windows")]  { Box::new(windows::WindowsBackend) }
    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    { Box::new(NullBackend) }
}

#[allow(dead_code)]
pub struct NullBackend;

#[allow(dead_code)]
impl Backend for NullBackend {
    fn now(&self) -> Track { Track::stopped() }
}
