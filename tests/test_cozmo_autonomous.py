"""Tests for iphone-cozmo/cozmo_autonomous.py's per-tick decision loop.
call_claude() is monkeypatched out (no real network call, no API key
needed) so these check the control flow: does one_tick() call the right
robot command, include the camera frame when available, and degrade
gracefully when no frame arrives in time."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_autonomous as ca


class FakeLink:
    def __init__(self, image=b"\xff\xd8fakejpeg\xff\xd9"):
        self.calls = []
        self._image = image

    def capture_image(self, timeout=3.0):
        return self._image

    def drive(self, direction): self.calls.append(("drive", direction))
    def turn(self, direction): self.calls.append(("turn", direction))
    def head(self, direction): self.calls.append(("look", direction))
    def lights(self, color): self.calls.append(("lights", color))


def _tool_response(name, tool_input, text=None):
    content = []
    if text:
        content.append({"type": "text", "text": text})
    content.append({"type": "tool_use", "id": "t1", "name": name, "input": tool_input})
    return {"content": content}


class TestRunTool(unittest.TestCase):
    def test_every_tool_dispatches_correctly(self):
        link = FakeLink()
        ca.run_tool(link, "drive", {"direction": "forward"})
        ca.run_tool(link, "turn", {"direction": "right"})
        ca.run_tool(link, "look", {"direction": "up"})
        ca.run_tool(link, "lights", {"color": "red"})
        wait_result = ca.run_tool(link, "wait", {})
        self.assertEqual(link.calls, [
            ("drive", "forward"), ("turn", "right"), ("look", "up"), ("lights", "red"),
        ])
        self.assertIn("watching", wait_result)

    def test_unknown_tool_does_not_crash(self):
        result = ca.run_tool(FakeLink(), "somersault", {})
        self.assertIn("Unknown tool", result)


class TestOneTick(unittest.TestCase):
    def test_includes_camera_frame_when_available(self):
        link = FakeLink(image=b"\xff\xd8realjpeg\xff\xd9")
        recent = []
        captured_messages = {}

        def fake_call_claude(messages):
            captured_messages["messages"] = messages
            return _tool_response("wait", {})

        with patch.object(ca, "call_claude", side_effect=fake_call_claude):
            ca.one_tick(link, recent)

        content = captured_messages["messages"][0]["content"]
        types = [b["type"] for b in content]
        self.assertIn("image", types)
        image_block = next(b for b in content if b["type"] == "image")
        self.assertEqual(image_block["source"]["media_type"], "image/jpeg")
        # base64 round-trips back to the original JPEG bytes
        import base64
        self.assertEqual(base64.b64decode(image_block["source"]["data"]), link._image)

    def test_missing_camera_frame_still_completes_a_tick(self):
        link = FakeLink(image=None)
        recent = []
        with patch.object(ca, "call_claude", return_value=_tool_response("turn", {"direction": "left"})):
            ca.one_tick(link, recent)
        self.assertEqual(link.calls, [("turn", "left")])

    def test_tool_call_executes_and_is_recorded_in_recent_actions(self):
        link = FakeLink()
        recent = []
        with patch.object(ca, "call_claude",
                           return_value=_tool_response("drive", {"direction": "forward"}, text="Onward!")):
            ca.one_tick(link, recent)
        self.assertEqual(link.calls, [("drive", "forward")])
        self.assertEqual(len(recent), 1)

    def test_recent_actions_list_is_capped_at_five(self):
        link = FakeLink()
        recent = []
        with patch.object(ca, "call_claude", return_value=_tool_response("wait", {})):
            for _ in range(8):
                ca.one_tick(link, recent)
        self.assertEqual(len(recent), 5)


class TestApiKeyGuard(unittest.TestCase):
    def test_main_refuses_to_connect_with_the_placeholder_key(self):
        with patch.object(ca, "API_KEY", "PASTE_YOUR_KEY_HERE"), \
             patch.object(ca, "CozmoLink") as mock_link_cls:
            ca.main()
        mock_link_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
