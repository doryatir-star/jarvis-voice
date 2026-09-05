"""Unit tests for cozmo_hub.py's non-network logic (speed/direction math,
head/lift/lights dispatch) using a fake pycozmo-style client — no real
Wi-Fi or hardware needed."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cozmo_hub


class FakeClient:
    def __init__(self):
        self.calls = []

    def drive_wheels(self, lwheel_speed, rwheel_speed, duration=None, **kw):
        self.calls.append(("drive_wheels", lwheel_speed, rwheel_speed, duration))

    def stop_all_motors(self):
        self.calls.append(("stop_all_motors",))

    def set_head_angle(self, angle, **kw):
        self.calls.append(("set_head_angle", angle))

    def set_lift_height(self, height, **kw):
        self.calls.append(("set_lift_height", height))

    def set_all_backpack_lights(self, light):
        self.calls.append(("set_all_backpack_lights", light))

    def play_anim(self, name):
        self.calls.append(("play_anim", name))

    def disconnect(self):
        self.calls.append(("disconnect",))

    def stop(self):
        self.calls.append(("stop",))


def make_connected_hub(**kwargs):
    hub = cozmo_hub.CozmoHub(drive_speed=100.0, drive_seconds=0.05,
                              turn_speed=80.0, turn_seconds=0.05, **kwargs)
    hub._client = FakeClient()
    hub._connected.set()
    hub._anims_loaded = True
    return hub


class TestNoPycozmoInstalled(unittest.TestCase):
    def test_start_reports_error_when_pycozmo_missing(self):
        if cozmo_hub._PYCOZMO_OK:
            self.skipTest("pycozmo is installed in this environment")
        errors = []
        hub = cozmo_hub.CozmoHub(on_error=lambda m: errors.append(m))
        hub.start()
        self.assertFalse(hub.is_connected())
        self.assertTrue(errors)


class TestDisconnectedDegradesGracefully(unittest.TestCase):
    def test_every_command_returns_a_string_when_not_connected(self):
        hub = cozmo_hub.CozmoHub()
        self.assertFalse(hub.is_connected())
        self.assertEqual(hub.drive("forward"), "Cozmo isn't connected.")
        self.assertEqual(hub.turn("left"), "Cozmo isn't connected.")
        self.assertEqual(hub.stop_all(), "Cozmo isn't connected.")
        self.assertEqual(hub.turn_head("up"), "Cozmo isn't connected.")
        self.assertEqual(hub.lift("up"), "Cozmo isn't connected.")
        self.assertEqual(hub.lights("red"), "Cozmo isn't connected.")
        self.assertEqual(hub.play_anim("anim_foo"), "Cozmo isn't connected.")


class TestConnectedMotorLogic(unittest.TestCase):
    def test_drive_forward_uses_positive_speed_on_both_wheels(self):
        hub = make_connected_hub()
        hub.drive("forward")
        self.assertEqual(hub._client.calls[-1], ("drive_wheels", 100.0, 100.0, 0.05))

    def test_drive_backward_uses_negative_speed_on_both_wheels(self):
        hub = make_connected_hub()
        hub.drive("backward")
        self.assertEqual(hub._client.calls[-1], ("drive_wheels", -100.0, -100.0, 0.05))

    def test_turn_left_is_differential(self):
        hub = make_connected_hub()
        hub.turn("left")
        self.assertEqual(hub._client.calls[-1], ("drive_wheels", -80.0, 80.0, 0.05))

    def test_turn_right_is_differential(self):
        hub = make_connected_hub()
        hub.turn("right")
        self.assertEqual(hub._client.calls[-1], ("drive_wheels", 80.0, -80.0, 0.05))

    def test_speeds_are_clamped_to_hardware_max(self):
        hub = cozmo_hub.CozmoHub(drive_speed=999.0, turn_speed=999.0)
        self.assertEqual(hub.drive_speed, cozmo_hub.MAX_WHEEL_SPEED_MMPS)
        self.assertEqual(hub.turn_speed, cozmo_hub.MAX_WHEEL_SPEED_MMPS)

    def test_stop_all_calls_stop_all_motors(self):
        hub = make_connected_hub()
        hub.stop_all()
        self.assertIn(("stop_all_motors",), hub._client.calls)

    def test_head_up_down_center_map_to_expected_angles(self):
        hub = make_connected_hub()
        hub.turn_head("up")
        hub.turn_head("down")
        hub.turn_head("center")
        angles = [c[1] for c in hub._client.calls if c[0] == "set_head_angle"]
        self.assertAlmostEqual(angles[0], math.radians(cozmo_hub.HEAD_UP_DEG))
        self.assertAlmostEqual(angles[1], math.radians(cozmo_hub.HEAD_DOWN_DEG))
        self.assertAlmostEqual(angles[2], 0.0)

    def test_lift_up_down_map_to_hardware_extremes(self):
        hub = make_connected_hub()
        hub.lift("up")
        hub.lift("down")
        heights = [c[1] for c in hub._client.calls if c[0] == "set_lift_height"]
        self.assertEqual(heights[0], cozmo_hub.MAX_LIFT_HEIGHT_MM)
        self.assertEqual(heights[1], cozmo_hub.MIN_LIFT_HEIGHT_MM)

    def test_lights_rejects_unknown_color(self):
        hub = make_connected_hub()
        result = hub.lights("purple")
        self.assertIn("purple", result)
        self.assertFalse(hub._client.calls)

    def test_lights_known_color_calls_set_all_backpack_lights(self):
        hub = make_connected_hub()
        hub.lights("green")
        self.assertEqual(hub._client.calls[-1][0], "set_all_backpack_lights")

    def test_play_anim_without_loaded_anims_returns_friendly_error(self):
        hub = make_connected_hub()
        hub._anims_loaded = False
        result = hub.play_anim("anim_greeting_happy_01")
        self.assertIn("didn't load", result)
        self.assertFalse(hub._client.calls)

    def test_play_anim_passes_name_through(self):
        hub = make_connected_hub()
        hub.play_anim("anim_greeting_happy_01")
        self.assertIn(("play_anim", "anim_greeting_happy_01"), hub._client.calls)


if __name__ == "__main__":
    unittest.main()
