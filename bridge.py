#!/usr/bin/env python3
# mpris bridge for the pomodoro timer.
# wraps `playerctl` so the browser can read & control whatever is playing
# (spotify desktop, netease cloud, mpd, browser players — anything mpris).
#
# requires: playerctl   (pacman -S playerctl)
# run:      python bridge.py
# then in timer settings: enable music bridge, url http://localhost:7777

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 7777
SEP = "\x1f"  # ascii unit separator — won't appear in real metadata
FIELDS = ["playerName", "status", "title", "artist", "album", "mpris:artUrl"]
FMT = SEP.join("{{" + f + "}}" for f in FIELDS)


def playerctl(*args):
    try:
        r = subprocess.run(
            ["playerctl", *args],
            capture_output=True, text=True, timeout=1.5,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def now():
    raw = playerctl("metadata", "--format", FMT)
    if not raw:
        return {"status": "stopped", "player": "", "title": "", "artist": "", "album": "", "art": ""}
    parts = (raw.split(SEP) + [""] * 6)[:6]
    player, status, title, artist, album, art = parts
    return {
        "player": player,
        "status": (status or "stopped").lower(),
        "title": title,
        "artist": artist,
        "album": album,
        "art": art,
    }


CONTROLS = {"/play-pause": "play-pause", "/next": "next", "/previous": "previous"}


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/now":
            self._json(200, now())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        cmd = CONTROLS.get(self.path)
        if not cmd:
            self._json(404, {"error": "not found"})
            return
        playerctl(cmd)
        self._json(200, now())

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print(f"mpris bridge on http://{HOST}:{PORT}")
    print("endpoints: GET /now  ·  POST /play-pause  /next  /previous")
    try:
        ThreadingHTTPServer((HOST, PORT), H).serve_forever()
    except KeyboardInterrupt:
        pass
