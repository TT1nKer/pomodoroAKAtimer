import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from pomodoro_sync_api import SyncStore, build_server, normalize_stats_log


class NormalizeStatsLogTests(unittest.TestCase):
    def test_sorts_and_deduplicates_entries(self):
        now = int(time.time() * 1000)
        entry = {"ts": now, "type": "focus", "min": 25}
        self.assertEqual(normalize_stats_log([entry, entry]), [entry])

    def test_rejects_non_focus_and_out_of_range_minutes(self):
        now = int(time.time() * 1000)
        with self.assertRaises(ValueError):
            normalize_stats_log([{"ts": now, "type": "short", "min": 5}])
        with self.assertRaises(ValueError):
            normalize_stats_log([{"ts": now, "type": "focus", "min": 0}])

    def test_internal_merge_caps_after_deduplication(self):
        now = int(time.time() * 1000)
        entries = [
            {"ts": now - index * 1000, "type": "focus", "min": 25}
            for index in range(10_005)
        ]
        self.assertEqual(len(normalize_stats_log(entries, enforce_input_limit=False)), 10_000)


class SyncStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = SyncStore(Path(self.temporary_directory.name) / "sync.sqlite3")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_oauth_state_is_single_use(self):
        state = self.store.create_oauth_state()
        self.assertTrue(self.store.consume_oauth_state(state))
        self.assertFalse(self.store.consume_oauth_state(state))

    def test_users_have_isolated_stats(self):
        first_token = self.store.login_google_user("google-a", "a@example.com")
        second_token = self.store.login_google_user("google-b", "b@example.com")
        first_user = self.store.user_for_token(first_token)
        second_user = self.store.user_for_token(second_token)
        now = int(time.time() * 1000)
        self.store.merge_stats(first_user["id"], [{"ts": now, "type": "focus", "min": 25}])
        self.assertEqual(len(self.store.read_stats(first_user["id"])), 1)
        self.assertEqual(self.store.read_stats(second_user["id"]), [])

    def test_merge_preserves_concurrent_device_entries(self):
        token = self.store.login_google_user("google-a", "a@example.com")
        user = self.store.user_for_token(token)
        now = int(time.time() * 1000)
        first = {"ts": now - 1000, "type": "focus", "min": 25}
        second = {"ts": now, "type": "focus", "min": 50}
        self.store.merge_stats(user["id"], [first])
        merged = self.store.merge_stats(user["id"], [second])
        self.assertEqual(merged, [first, second])

    def test_logout_invalidates_session(self):
        token = self.store.login_google_user("google-a", "a@example.com")
        self.assertIsNotNone(self.store.user_for_token(token))
        self.store.logout(token)
        self.assertIsNone(self.store.user_for_token(token))

    def test_delete_stats_does_not_delete_user(self):
        token = self.store.login_google_user("google-a", "a@example.com")
        user = self.store.user_for_token(token)
        now = int(time.time() * 1000)
        self.store.merge_stats(user["id"], [{"ts": now, "type": "focus", "min": 25}])
        self.store.delete_stats(user["id"])
        self.assertEqual(self.store.read_stats(user["id"]), [])
        self.assertIsNotNone(self.store.user_for_token(token))


class SyncApiHttpTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.server = build_server(
            "127.0.0.1",
            0,
            Path(self.temporary_directory.name) / "sync.sqlite3",
            "https://ttinker.net",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def request(self, path, *, method="GET", origin=None, body=None):
        headers = {}
        if origin:
            headers["Origin"] = origin
        data = json.dumps(body).encode() if body is not None else None
        if data:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            try:
                return error.code, json.loads(error.read())
            finally:
                error.close()

    def test_session_reports_unconfigured_google_beta(self):
        status, payload = self.request("/session")
        self.assertEqual(status, 200)
        self.assertFalse(payload["authenticated"])
        self.assertFalse(payload["configured"])

    def test_google_start_fails_closed_without_credentials(self):
        status, payload = self.request("/oauth/google/start")
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"], "google beta is not configured")

    def test_write_requires_exact_origin(self):
        status, payload = self.request("/logout", method="POST")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "invalid origin")

    def test_stats_requires_login(self):
        status, payload = self.request("/stats")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "login required")


if __name__ == "__main__":
    unittest.main()
