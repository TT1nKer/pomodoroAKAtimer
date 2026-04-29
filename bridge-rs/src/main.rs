// timer-bridge: tiny http server that exposes the desktop media player
// to the timer ui. wire-compatible with the python bridge.py.
//
// endpoints:
//   GET  /now           -> { player, status, title, artist, album, art }
//   POST /play-pause    -> /now after toggle
//   POST /next          -> /now after skip
//   POST /previous      -> /now after skip back

use std::sync::Arc;
use tiny_http::{Header, Method, Response, Server};

mod backend;
use backend::Backend;

const HOST: &str = "127.0.0.1";
const PORT: u16 = 7777;

fn main() {
    let backend: Arc<dyn Backend> = backend::default_backend().into();
    let addr = format!("{HOST}:{PORT}");
    let server = Server::http(&addr).expect("bind 127.0.0.1:7777");
    eprintln!("media bridge on http://{addr}");
    eprintln!("endpoints: GET /now  ·  POST /play-pause  /next  /previous");

    for req in server.incoming_requests() {
        let body = route(&*backend, req.method(), req.url());
        let resp = Response::from_string(body)
            .with_header(hdr("Access-Control-Allow-Origin", "*"))
            .with_header(hdr("Access-Control-Allow-Methods", "GET, POST, OPTIONS"))
            .with_header(hdr("Access-Control-Allow-Headers", "Content-Type"))
            .with_header(hdr("Content-Type", "application/json"));
        let _ = req.respond(resp);
    }
}

fn route(backend: &dyn Backend, method: &Method, path: &str) -> String {
    match (method, path) {
        (Method::Options, _) => "{}".into(),
        (Method::Get, "/now") => to_json(&backend.now()),
        (Method::Post, "/play-pause") => { backend.play_pause(); to_json(&backend.now()) }
        (Method::Post, "/next") => { backend.next(); to_json(&backend.now()) }
        (Method::Post, "/previous") => { backend.previous(); to_json(&backend.now()) }
        _ => r#"{"error":"not found"}"#.into(),
    }
}

fn to_json<T: serde::Serialize>(v: &T) -> String {
    serde_json::to_string(v).unwrap_or_else(|_| "{}".into())
}

fn hdr(name: &str, value: &str) -> Header {
    format!("{name}: {value}").parse().expect("header")
}
