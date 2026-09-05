"""Tests for iphone-cozmo/cozmo_ai.py's tool-calling loop. call_claude() is
monkeypatched out (no real network call, no API key needed) so these check
the control flow: does it execute the right robot command for a given
Claude response, append messages correctly, and stop looping once Claude
replies with plain text instead of another tool call."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_ai as ca


class FakeLink:
    def __init__(self):
        self.calls = []

    def drive(self, direction): self.calls.append(("drive", direction))
    def turn(self, direction): self.calls.append(("turn", direction))
    def stop(self): self.calls.append(("stop",))
    def head(self, direction): self.calls.append(("head", direction))
    def lift(self, direction): self.calls.append(("lift", direction))
    def lights(self, color): self.calls.append(("lights", color))


def _text_response(text):
    return {"content": [{"type": "text", "text": text}]}


def _tool_response(name, tool_input, tool_id="toolu_1"):
    return {"content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}]}


class TestRunTool(unittest.TestCase):
    def test_every_tool_name_dispatches_to_the_right_link_method(self):
        link = FakeLink()
        ca.run_tool(link, "drive", {"direction": "forward"})
        ca.run_tool(link, "turn", {"direction": "left"})
        ca.run_tool(link, "stop", {})
        ca.run_tool(link, "head", {"direction": "up"})
        ca.run_tool(link, "lift", {"direction": "down"})
        ca.run_tool(link, "lights", {"color": "green"})
        self.assertEqual(link.calls, [
            ("drive", "forward"), ("turn", "left"), ("stop",),
            ("head", "up"), ("lift", "down"), ("lights", "green"),
        ])

    def test_unknown_tool_name_does_not_crash(self):
        link = FakeLink()
        result = ca.run_tool(link, "moonwalk", {})
        self.assertIn("Unknown tool", result)
        self.assertEqual(link.calls, [])


class TestThinkLoop(unittest.TestCase):
    def test_plain_text_reply_stops_after_one_call(self):
        link = FakeLink()
        messages = []
        with patch.object(ca, "call_claude", return_value=_text_response("Hi there!")) as mock_call:
            ca.think(link, messages, "hello")
        mock_call.assert_called_once()
        self.assertEqual(link.calls, [])
        # user message, then assistant reply -- exactly two turns recorded.
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], {"role": "user", "content": "hello"})

    def test_tool_use_executes_the_command_then_continues_the_loop(self):
        link = FakeLink()
        messages = []
        responses = [
            _tool_response("drive", {"direction": "forward"}),
            _text_response("Zoom! Done."),
        ]
        with patch.object(ca, "call_claude", side_effect=responses) as mock_call:
            ca.think(link, messages, "go forward")
        self.assertEqual(mock_call.call_count, 2)
        self.assertEqual(link.calls, [("drive", "forward")])
        # user, assistant(tool_use), user(tool_result), assistant(text)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[2]["content"][0]["type"], "tool_result")
        self.assertEqual(messages[2]["content"][0]["tool_use_id"], "toolu_1")

    def test_multiple_tool_calls_in_one_turn_all_execute(self):
        link = FakeLink()
        messages = []

        def two_tools_response():
            return {"content": [
                {"type": "tool_use", "id": "a", "name": "head", "input": {"direction": "up"}},
                {"type": "tool_use", "id": "b", "name": "lights", "input": {"color": "blue"}},
            ]}

        responses = [two_tools_response(), _text_response("There!")]
        with patch.object(ca, "call_claude", side_effect=responses):
            ca.think(link, messages, "look up and go blue")
        self.assertEqual(link.calls, [("head", "up"), ("lights", "blue")])
        # Both tool_results must land in a single user message (API rule),
        # not split across two.
        tool_result_msgs = [m for m in messages if m["role"] == "user" and
                             isinstance(m["content"], list)]
        self.assertEqual(len(tool_result_msgs), 1)
        self.assertEqual(len(tool_result_msgs[0]["content"]), 2)

    def test_conversation_history_accumulates_across_calls(self):
        link = FakeLink()
        messages = []
        with patch.object(ca, "call_claude", return_value=_text_response("Hi!")):
            ca.think(link, messages, "hello")
        with patch.object(ca, "call_claude", return_value=_text_response("Still here!")):
            ca.think(link, messages, "you there?")
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[2], {"role": "user", "content": "you there?"})


class TestApiKeyGuard(unittest.TestCase):
    def test_main_refuses_to_connect_with_the_placeholder_key(self):
        # main() must bail out before ever touching CozmoLink (i.e. before
        # trying to talk to Cozmo at all) if no real API key was set --
        # it should never send the literal placeholder string to Anthropic.
        with patch.object(ca, "API_KEY", "PASTE_YOUR_KEY_HERE"), \
             patch.object(ca, "CozmoLink") as mock_link_cls:
            ca.main()
        mock_link_cls.assert_not_called()

    def test_main_refuses_to_connect_with_an_empty_key(self):
        with patch.object(ca, "API_KEY", ""), \
             patch.object(ca, "CozmoLink") as mock_link_cls:
            ca.main()
        mock_link_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
