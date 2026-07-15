"""Unit tests for the robot_* dispatcher plumbing in commands.py, using a
stub hub — no real Bluetooth or hardware needed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import commands


class StubHub:
    def __init__(self):
        self.calls = []

    def is_connected(self):
        return True

    def drive(self, direction):
        self.calls.append(("drive", direction))
        return f"stub drive {direction}"

    def turn(self, direction):
        self.calls.append(("turn", direction))
        return f"stub turn {direction}"

    def stop_all(self):
        self.calls.append(("stop_all",))
        return "stub stop"

    def turn_head(self, direction):
        self.calls.append(("turn_head", direction))
        return f"stub head {direction}"

    def claw(self, action):
        self.calls.append(("claw", action))
        return f"stub claw {action}"


class TestRobotDispatchNoHub(unittest.TestCase):
    def setUp(self):
        commands.set_robot_hub(None)

    def test_all_robot_actions_report_not_connected(self):
        for action, value in [
            ("robot_forward", ""), ("robot_backward", ""), ("robot_turn", "left"),
            ("robot_stop", ""), ("robot_head", "left"), ("robot_claw", "open"),
        ]:
            with self.subTest(action=action):
                self.assertEqual(commands.execute(action, value), "The rover isn't connected.")


class TestRobotDispatchWithStubHub(unittest.TestCase):
    def setUp(self):
        self.hub = StubHub()
        commands.set_robot_hub(self.hub)

    def tearDown(self):
        commands.set_robot_hub(None)

    def test_forward_routes_to_drive_forward(self):
        self.assertEqual(commands.execute("robot_forward", ""), "stub drive forward")
        self.assertIn(("drive", "forward"), self.hub.calls)

    def test_backward_routes_to_drive_backward(self):
        self.assertEqual(commands.execute("robot_backward", ""), "stub drive backward")
        self.assertIn(("drive", "backward"), self.hub.calls)

    def test_turn_passes_direction_through(self):
        commands.execute("robot_turn", "left")
        self.assertIn(("turn", "left"), self.hub.calls)

    def test_stop_routes_to_stop_all(self):
        commands.execute("robot_stop", "")
        self.assertIn(("stop_all",), self.hub.calls)

    def test_head_passes_direction_through(self):
        commands.execute("robot_head", "right")
        self.assertIn(("turn_head", "right"), self.hub.calls)

    def test_claw_passes_action_through(self):
        commands.execute("robot_claw", "close")
        self.assertIn(("claw", "close"), self.hub.calls)


if __name__ == "__main__":
    unittest.main()
