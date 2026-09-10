"""Tests for iphone-cozmo/cozmo_web.py's HTTP API: starts a real local
server (on an OS-assigned port) with a FakeLink standing in for a real
Cozmo connection, and drives it with real HTTP requests via urllib -- no
network access, no API key, no real robot needed."""
import json
import os
import socketserver
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_web as cw


class FakeLink:
    def __init__(self):
        self.calls = []

    def drive(self, direction): self.calls.append(("drive", direction))
    def turn(self, direction): self.calls.append(("turn", direction))
    def stop(self): self.calls.append(("stop",))
    def head(self, direction): self.calls.append(("head", direction))
    def lift(self, direction): self.calls.append(("lift", direction))
    def lights(self, color): self.calls.append(("lights", color))


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


if __name__ == "__main__":
    unittest.main()
