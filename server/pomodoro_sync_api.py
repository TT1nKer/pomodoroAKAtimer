#!/usr/bin/env python3
"""Same-origin Google login and stats sync service for the Pomodoro beta."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import time
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


COOKIE_NAME = "pomodoro_beta_session"
OAUTH_STATE_COOKIE_NAME = "pomodoro_beta_oauth_state"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
OAUTH_STATE_TTL_SECONDS = 10 * 60
MAX_BODY_BYTES = 256 * 1024
MAX_STATS_ENTRIES = 10_000
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def normalize_stats_log(value: Any, *, enforce_input_limit: bool = True) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (enforce_input_limit and len(value) > MAX_STATS_ENTRIES):
        raise ValueError("log must contain at most 10000 entries")
    now_limit = int(time.time() * 1000) + 24 * 60 * 60 * 1000
    earliest = 1_577_836_800_000
    normalized: dict[tuple[int, int], dict[str, Any]] = {}
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("every log entry must be an object")
        timestamp, minutes = entry.get("ts"), entry.get("min")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("entry timestamp is invalid")
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)):
            raise ValueError("entry minutes are invalid")
        timestamp, minutes = int(timestamp), int(minutes)
        if entry.get("type") != "focus" or not earliest <= timestamp <= now_limit or not 1 <= minutes <= 240:
            raise ValueError("entry values are outside the accepted range")
        normalized[(timestamp, minutes)] = {"ts": timestamp, "type": "focus", "min": minutes}
    ordered = sorted(normalized.values(), key=lambda entry: entry["ts"])
    return ordered[-MAX_STATS_ENTRIES:]


class SyncStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    google_sub TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash BLOB PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state_hash BLOB PRIMARY KEY,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stats (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    log_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expires_at ON sessions(expires_at);
                """
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def token_hash(token: str) -> bytes:
        return hashlib.sha256(token.encode()).digest()

    def create_oauth_state(self) -> str:
        state = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.connect() as connection:
            connection.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO oauth_states(state_hash, expires_at) VALUES (?, ?)",
                (self.token_hash(state), now + OAUTH_STATE_TTL_SECONDS),
            )
        return state

    def consume_oauth_state(self, state: str) -> bool:
        now = int(time.time())
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM oauth_states WHERE state_hash = ? AND expires_at > ?",
                (self.token_hash(state), now),
            )
            return cursor.rowcount == 1

    def login_google_user(self, google_sub: str, email: str) -> str:
        now = int(time.time())
        token = secrets.token_urlsafe(32)
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
            if row:
                user_id = row["id"]
                connection.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
            else:
                user_id = connection.execute(
                    "INSERT INTO users(google_sub, email, created_at) VALUES (?, ?, ?)",
                    (google_sub, email, now),
                ).lastrowid
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (self.token_hash(token), user_id, now + SESSION_TTL_SECONDS),
            )
        return token

    def user_for_token(self, token: str | None) -> sqlite3.Row | None:
        if not token:
            return None
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT users.id, users.email FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                """,
                (self.token_hash(token), int(time.time())),
            ).fetchone()

    def logout(self, token: str | None) -> None:
        if token:
            with self.connect() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (self.token_hash(token),))

    def read_stats(self, user_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("SELECT log_json FROM stats WHERE user_id = ?", (user_id,)).fetchone()
            return json.loads(row["log_json"]) if row else []

    def merge_stats(self, user_id: int, incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT log_json FROM stats WHERE user_id = ?", (user_id,)).fetchone()
            existing = json.loads(row["log_json"]) if row else []
            merged = normalize_stats_log(existing + incoming, enforce_input_limit=False)
            connection.execute(
                """
                INSERT INTO stats(user_id, log_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET log_json = excluded.log_json, updated_at = excluded.updated_at
                """,
                (user_id, json.dumps(merged, separators=(",", ":")), int(time.time())),
            )
            return merged

    def delete_stats(self, user_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM stats WHERE user_id = ?", (user_id,))


class SyncApiHandler(BaseHTTPRequestHandler):
    server_version = "PomodoroSync/1"
    store: SyncStore
    allowed_origin: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    def do_GET(self) -> None:
        route = urllib.parse.urlsplit(self.path).path
        if route == "/oauth/google/start":
            self.start_google_oauth()
        elif route == "/oauth/google/callback":
            self.finish_google_oauth()
        elif route == "/session":
            user = self.authenticated_user()
            self.send_json(HTTPStatus.OK, {
                "authenticated": bool(user),
                "email": user["email"] if user else None,
                "configured": self.google_is_configured(),
            })
        elif route == "/stats":
            user = self.require_user()
            if user:
                self.send_json(HTTPStatus.OK, {"log": self.store.read_stats(user["id"])})
        else:
            self.send_error_json(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        route = urllib.parse.urlsplit(self.path).path
        if not self.has_valid_origin():
            self.send_error_json(HTTPStatus.FORBIDDEN, "invalid origin")
        elif route == "/logout":
            self.store.logout(self.session_token())
            self.send_json(HTTPStatus.OK, {"authenticated": False}, clear_cookie=True)
        elif route == "/stats":
            user = self.require_user()
            if user:
                try:
                    log = normalize_stats_log(self.read_json().get("log"))
                except (ValueError, AttributeError) as error:
                    self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                    return
                self.send_json(HTTPStatus.OK, {"log": self.store.merge_stats(user["id"], log)})
        else:
            self.send_error_json(HTTPStatus.NOT_FOUND, "not found")

    def do_DELETE(self) -> None:
        if urllib.parse.urlsplit(self.path).path != "/stats":
            self.send_error_json(HTTPStatus.NOT_FOUND, "not found")
        elif not self.has_valid_origin():
            self.send_error_json(HTTPStatus.FORBIDDEN, "invalid origin")
        else:
            user = self.require_user()
            if user:
                self.store.delete_stats(user["id"])
                self.send_json(HTTPStatus.OK, {"log": []})

    def google_is_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    def start_google_oauth(self) -> None:
        if not self.google_is_configured():
            self.send_error_json(HTTPStatus.SERVICE_UNAVAILABLE, "google beta is not configured")
            return
        state = self.store.create_oauth_state()
        query = urllib.parse.urlencode({
            "client_id": self.google_client_id,
            "redirect_uri": self.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email",
            "state": state,
            "prompt": "select_account",
        })
        self.redirect(GOOGLE_AUTH_URL + "?" + query, oauth_state=state)

    def finish_google_oauth(self) -> None:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        state, code = query.get("state", [""])[0], query.get("code", [""])[0]
        state_cookie = self.cookie_value(OAUTH_STATE_COOKIE_NAME)
        state_matches = bool(state and state_cookie and secrets.compare_digest(state, state_cookie))
        if not self.google_is_configured() or not code or not state_matches or not self.store.consume_oauth_state(state):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "invalid oauth response")
            return
        try:
            token_request = urllib.request.Request(
                GOOGLE_TOKEN_URL,
                data=urllib.parse.urlencode({
                    "code": code,
                    "client_id": self.google_client_id,
                    "client_secret": self.google_client_secret,
                    "redirect_uri": self.google_redirect_uri,
                    "grant_type": "authorization_code",
                }).encode(),
                method="POST",
            )
            with urllib.request.urlopen(token_request, timeout=8) as response:
                id_token = json.loads(response.read()).get("id_token")
            if not id_token:
                raise ValueError("missing identity token")
            tokeninfo_url = GOOGLE_TOKENINFO_URL + "?id_token=" + urllib.parse.quote(id_token)
            with urllib.request.urlopen(tokeninfo_url, timeout=8) as response:
                identity = json.loads(response.read())
            if identity.get("aud") != self.google_client_id or identity.get("email_verified") != "true":
                raise ValueError("unverified identity")
            google_sub, email = identity.get("sub"), identity.get("email", "").lower()
            if not google_sub or not email:
                raise ValueError("incomplete identity")
            token = self.store.login_google_user(google_sub, email)
        except (OSError, ValueError, json.JSONDecodeError):
            self.send_error_json(HTTPStatus.BAD_GATEWAY, "google login failed")
            return
        self.redirect("/pomodoro/?beta=connected", session_token=token, clear_oauth_state=True)

    def authenticated_user(self) -> sqlite3.Row | None:
        return self.store.user_for_token(self.session_token())

    def require_user(self) -> sqlite3.Row | None:
        user = self.authenticated_user()
        if user is None:
            self.send_error_json(HTTPStatus.UNAUTHORIZED, "login required")
        return user

    def session_token(self) -> str | None:
        return self.cookie_value(COOKIE_NAME)

    def cookie_value(self, name: str) -> str | None:
        morsel = SimpleCookie(self.headers.get("Cookie", "")).get(name)
        return morsel.value if morsel else None

    def has_valid_origin(self) -> bool:
        return self.headers.get("Origin") == self.allowed_origin

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid content length") from error
        if not 0 < length <= MAX_BODY_BYTES:
            raise ValueError("request body is empty or too large")
        try:
            value = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("request body must be valid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def redirect(
        self,
        location: str,
        session_token: str | None = None,
        oauth_state: str | None = None,
        clear_oauth_state: bool = False,
    ) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        if session_token:
            self.send_header("Set-Cookie", self.session_cookie(session_token, SESSION_TTL_SECONDS))
        if oauth_state:
            self.send_header("Set-Cookie", self.oauth_state_cookie(oauth_state, OAUTH_STATE_TTL_SECONDS))
        elif clear_oauth_state:
            self.send_header("Set-Cookie", self.oauth_state_cookie("", 0))
        self.end_headers()

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json(status, {"error": message})

    def send_json(self, status: HTTPStatus, payload: dict[str, Any], *, clear_cookie: bool = False) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if clear_cookie:
            self.send_header("Set-Cookie", self.session_cookie("", 0))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def session_cookie(token: str, max_age: int) -> str:
        return f"{COOKIE_NAME}={token}; Path=/pomodoro/; Max-Age={max_age}; HttpOnly; Secure; SameSite=Strict"

    @staticmethod
    def oauth_state_cookie(state: str, max_age: int) -> str:
        # Lax is required because Google's callback is a cross-site top-level navigation.
        return f"{OAUTH_STATE_COOKIE_NAME}={state}; Path=/pomodoro/api/beta/oauth/google/callback; Max-Age={max_age}; HttpOnly; Secure; SameSite=Lax"

    def log_message(self, format_string: str, *args: Any) -> None:
        # OAuth callbacks carry short-lived codes in the query string; never journal request URLs.
        return


def build_server(host: str, port: int, database_path: Path, allowed_origin: str) -> ThreadingHTTPServer:
    handler = type("ConfiguredSyncApiHandler", (SyncApiHandler,), {
        "store": SyncStore(database_path),
        "allowed_origin": allowed_origin,
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "google_redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", allowed_origin + "/pomodoro/api/beta/oauth/google/callback"),
    })
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("POMODORO_SYNC_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("POMODORO_SYNC_PORT", "8093")))
    parser.add_argument("--database", type=Path, default=Path(os.getenv("POMODORO_SYNC_DATABASE", "/var/lib/ttinker-pomodoro-sync/sync.sqlite3")))
    parser.add_argument("--origin", default=os.getenv("POMODORO_SYNC_ORIGIN", "https://ttinker.net"))
    args = parser.parse_args()
    server = build_server(args.host, args.port, args.database, args.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
