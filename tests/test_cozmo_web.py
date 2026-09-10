"""Tests for iphone-cozmo/cozmo_web.py's HTTP API: starts a real local
server (on an OS-assigned port) with a FakeLink standing in for a real
Cozmo connection, and drives it with real HTTP requests via urllib -- no
network access, no API key, no real robot needed."""
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_web as cw


class FakeLink:
    def __init__(self, image=None):
        self.calls = []
        self._image = image

    def drive(self, direction): self.calls.append(("drive", direction))
    def turn(self, direction): self.calls.append(("turn", direction))
    def stop(self): self.calls.append(("stop",))
    def head(self, direction): self.calls.append(("head", direction))
    def lift(self, direction): self.calls.append(("lift", direction))
    def lights(self, color): self.calls.append(("lights", color))
    def capture_image(self, timeout=3.0): return self._image


class TestCozmoWebApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_link = FakeLink()
        cw.link = cls.fake_link
        cls.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), cw.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.fake_link.calls.clear()

    def _url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def _post(self, path, body):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self._url(path), data=data, method="POST",
                                      headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_serves_the_control_page_at_root(self):
        with urllib.request.urlopen(self._url("/"), timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
        self.assertIn("<html", body)
        self.assertIn("Cozmo Control", body)

    @unittest.skipUnless(shutil.which("node"), "node isn't installed")
    def test_the_pages_inline_javascript_is_syntactically_valid(self):
        # Regression test: PAGE is a plain (non-raw) Python triple-quoted
        # string, so a literal like '\n' meant for the JS is silently
        # unescaped by Python into an actual newline character *before* it
        # ever reaches the browser -- turning a one-line JS string literal
        # into an unterminated one and crashing the whole script (which
        # then never reaches setStatus('Ready.'), leaving the page stuck
        # showing "Connecting..." forever with no visible error anywhere
        # except the browser console). Escaping it as '\\n' in this file's
        # source is what keeps the JS itself correct.
        script = re.search(r"<script>(.*?)</script>", cw.PAGE, re.S).group(1)
        result = subprocess.run(["node", "--check", "-"], input=script,
                                 capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_camera_returns_503_before_any_frame_arrives(self):
        try:
            urllib.request.urlopen(self._url("/api/camera"), timeout=5)
            self.fail("expected an HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 503)

    def test_camera_returns_latest_jpeg_once_available(self):
        with cw._latest_jpeg_lock:
            cw._latest_jpeg = b"\xff\xd8fakejpeg\xff\xd9"
        try:
            with urllib.request.urlopen(self._url("/api/camera"), timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers["Content-Type"], "image/jpeg")
                self.assertEqual(resp.read(), b"\xff\xd8fakejpeg\xff\xd9")
        finally:
            with cw._latest_jpeg_lock:
                cw._latest_jpeg = None

    def test_drive_dispatches_to_the_link_and_replies(self):
        status, data = self._post("/api/drive", {"direction": "forward"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertIn("forward", data["reply"])
        self.assertEqual(self.fake_link.calls, [("drive", "forward")])

    def test_turn_head_lift_lights_all_dispatch_correctly(self):
        self._post("/api/turn", {"direction": "left"})
        self._post("/api/head", {"direction": "up"})
        self._post("/api/lift", {"direction": "down"})
        self._post("/api/lights", {"color": "blue"})
        self.assertEqual(self.fake_link.calls, [
            ("turn", "left"), ("head", "up"), ("lift", "down"), ("lights", "blue"),
        ])

    def test_stop_takes_no_body(self):
        status, data = self._post("/api/stop", {})
        self.assertEqual(status, 200)
        self.assertEqual(self.fake_link.calls, [("stop",)])

    def test_chat_runs_free_form_text_through_think(self):
        status, data = self._post("/api/chat", {"text": "turn left"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(self.fake_link.calls, [("turn", "left")])

    def test_missing_required_field_is_a_400_not_a_crash(self):
        status, data = self._post("/api/drive", {})
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_unknown_api_path_is_a_400_not_a_crash(self):
        status, data = self._post("/api/somersault", {})
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_non_api_path_is_404(self):
        status, data = self._post("/nope", {})
        self.assertEqual(status, 404)

    def test_malformed_json_body_is_a_400_not_a_crash(self):
        req = urllib.request.Request(self._url("/api/drive"), data=b"not json",
                                      method="POST", headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("expected an HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)


class TestAiMode(unittest.TestCase):
    """Tests the /api/ai/* endpoints -- cozmo_autonomous.py's call_claude()
    is mocked out (no real network call, no API key needed), same as
    tests/test_cozmo_autonomous.py does for the standalone script."""

    @classmethod
    def setUpClass(cls):
        cls.fake_link = FakeLink()
        cw.link = cls.fake_link
        cls.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), cw.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.fake_link.calls.clear()

    def tearDown(self):
        # Safety net: make sure no test leaves a background AI loop running
        # into the next one, even if a test fails before reaching its own
        # stop+join.
        cw._ai_stop_event.set()
        if cw._ai_thread is not None:
            cw._ai_thread.join(timeout=2)
        cw._ai_stop_event.clear()
        with cw._ai_log_lock:
            cw._ai_log.clear()

    def _url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def _post(self, path):
        req = urllib.request.Request(self._url(path), data=b"{}", method="POST",
                                      headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def _get(self, path):
        with urllib.request.urlopen(self._url(path), timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_start_refuses_without_a_real_api_key(self):
        with patch.object(cw.ca, "API_KEY", "PASTE_YOUR_KEY_HERE"):
            status, data = self._post("/api/ai/start")
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])
        self.assertFalse(cw._ai_running)

    def test_start_runs_the_claude_loop_and_executes_actions(self):
        tool_response = {"content": [
            {"type": "text", "text": "Ooh, something to look at!"},
            {"type": "tool_use", "id": "t1", "name": "turn", "input": {"direction": "left"}},
        ]}
        # Keep the mock active for the whole start-wait-stop sequence -- the
        # background loop must never call the real (network) call_claude.
        with patch.object(cw.ca, "API_KEY", "sk-fake"), \
             patch.object(cw.ca, "TICK_SECONDS", 0.02), \
             patch.object(cw.ca, "call_claude", return_value=tool_response):
            status, data = self._post("/api/ai/start")
            self.assertEqual(status, 200)
            self.assertTrue(data["ok"])

            deadline = time.time() + 2
            while time.time() < deadline and not self.fake_link.calls:
                time.sleep(0.02)

            self.assertIn(("turn", "left"), self.fake_link.calls)
            status, log_data = self._get("/api/ai/log")
            self.assertTrue(log_data["running"])
            self.assertTrue(any("Turning left" in line for line in log_data["lines"]))

            self._post("/api/ai/stop")
            cw._ai_thread.join(timeout=2)

        self.assertFalse(cw._ai_running)

    def test_start_twice_does_not_spawn_a_second_loop(self):
        wait_response = {"content": [{"type": "tool_use", "id": "t1", "name": "wait", "input": {}}]}
        with patch.object(cw.ca, "API_KEY", "sk-fake"), \
             patch.object(cw.ca, "TICK_SECONDS", 0.02), \
             patch.object(cw.ca, "call_claude", return_value=wait_response):
            self._post("/api/ai/start")
            first_thread = cw._ai_thread
            status, data = self._post("/api/ai/start")
            self.assertEqual(status, 200)
            self.assertIn("already running", data["reply"])
            self.assertIs(cw._ai_thread, first_thread)

            self._post("/api/ai/stop")
            cw._ai_thread.join(timeout=2)

    def test_stop_when_not_running_says_so(self):
        status, data = self._post("/api/ai/stop")
        self.assertEqual(status, 200)
        self.assertIn("isn't running", data["reply"])


if __name__ == "__main__":
    unittest.main()
