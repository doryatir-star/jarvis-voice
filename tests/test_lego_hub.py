"""Unit tests for lego_hub.py's non-BLE logic (port resolution, motor
speed/direction math, auto-stop timer) using a fake pylgbst-style hub —
no real Bluetooth or hardware needed."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lego_hub


class FakeMotor:
    def __init__(self):
        self.calls = []

    def start_speed(self, primary, secondary=None):
        self.calls.append(("start_speed", primary, secondary))

    def stop(self):
        self.calls.append(("stop",))

    def angled(self, angle, speed_primary=0.4, wait_complete=False):
        self.calls.append(("angled", angle, speed_primary, wait_complete))


class FakeHub:
    def __init__(self):
        self.motor_AB = FakeMotor()
        self.port_C = FakeMotor()
        self.port_D = FakeMotor()


def make_connected_hub(**kwargs):
    hub = lego_hub.LegoHub(claw_port="D", head_port="C",
                            drive_speed=0.6, drive_seconds=0.05, turn_seconds=0.05,
                            **kwargs)
    hub._hub = FakeHub()
    hub._connected.set()
    return hub


class TestNoPylgbstInstalled(unittest.TestCase):
    def test_start_reports_error_when_pylgbst_missing(self):
        if lego_hub._PYLGBST_OK:
            self.skipTest("pylgbst is installed in this environment")
        errors = []
        hub = lego_hub.LegoHub(on_error=lambda m: errors.append(m))
        hub.start()
        self.assertFalse(hub.is_connected())
        self.assertTrue(errors)


class TestDisconnectedDegradesGracefully(unittest.TestCase):
    def test_every_command_returns_a_string_when_not_connected(self):
        hub = lego_hub.LegoHub()
        self.assertFalse(hub.is_connected())
        self.assertEqual(hub.drive("forward"), "The rover isn't connected.")
        self.assertEqual(hub.turn("left"), "The rover isn't connected.")
        self.assertEqual(hub.stop_all(), "The rover isn't connected.")
        self.assertEqual(hub.turn_head("left"), "The rover isn't connected.")
        self.assertEqual(hub.claw("open"), "The rover isn't connected.")


class TestConnectedMotorLogic(unittest.TestCase):
    def test_drive_forward_drives_both_treads_positive(self):
        hub = make_connected_hub()
        hub.drive("forward")
        self.assertEqual(hub._hub.motor_AB.calls[-1], ("start_speed", 0.6, 0.6))

    def test_drive_backward_drives_both_treads_negative(self):
        hub = make_connected_hub()
        hub.drive("backward")
        self.assertEqual(hub._hub.motor_AB.calls[-1], ("start_speed", -0.6, -0.6))

    def test_turn_left_is_differential(self):
        hub = make_connected_hub()
        hub.turn("left")
        self.assertEqual(hub._hub.motor_AB.calls[-1], ("start_speed", -0.6, 0.6))

    def test_turn_right_is_differential(self):
        hub = make_connected_hub()
        hub.turn("right")
        self.assertEqual(hub._hub.motor_AB.calls[-1], ("start_speed", 0.6, -0.6))

    def test_invert_flags_flip_polarity(self):
        hub = make_connected_hub(left_invert=True, right_invert=True)
        hub.drive("forward")
        self.assertEqual(hub._hub.motor_AB.calls[-1], ("start_speed", -0.6, -0.6))

    def test_claw_uses_configured_port(self):
        hub = make_connected_hub()
        hub.claw("open")
        self.assertTrue(hub._hub.port_D.calls)
        self.assertFalse(hub._hub.port_C.calls)

    def test_head_uses_configured_port(self):
        hub = make_connected_hub()
        hub.turn_head("left")
        self.assertTrue(hub._hub.port_C.calls)
        self.assertFalse(hub._hub.port_D.calls)

    def test_repeated_turn_left_does_not_over_rotate(self):
        # angled() is relative to current position — calling "turn left"
        # twice in a row must hold at -90, not walk to -180.
        hub = make_connected_hub()
        hub.turn_head("left")
        hub.turn_head("left")
        self.assertEqual(hub._hub.port_C.calls, [("angled", -90, 0.4, False)])

    def test_center_returns_head_to_zero_not_another_right_turn(self):
        hub = make_connected_hub()
        hub.turn_head("right")
        hub.turn_head("center")
        self.assertEqual(
            hub._hub.port_C.calls,
            [("angled", 90, 0.4, False), ("angled", -90, 0.4, False)],
        )

    def test_repeated_claw_open_does_not_over_rotate(self):
        hub = make_connected_hub()
        hub.claw("open")
        hub.claw("open")
        self.assertEqual(hub._hub.port_D.calls, [("angled", -60, 0.4, False)])

    def test_claw_close_after_open_returns_full_delta(self):
        hub = make_connected_hub()
        hub.claw("open")
        hub.claw("close")
        self.assertEqual(
            hub._hub.port_D.calls,
            [("angled", -60, 0.4, False), ("angled", 120, 0.4, False)],
        )

    def test_stop_all_cancels_pending_auto_stop_timer(self):
        hub = make_connected_hub()
        hub.drive("forward")
        hub.stop_all()
        calls_at_stop = list(hub._hub.motor_AB.calls)
        time.sleep(0.15)  # longer than drive_seconds=0.05
        # No extra ("stop",) call should have fired from the (cancelled) timer.
        self.assertEqual(hub._hub.motor_AB.calls, calls_at_stop)

    def test_auto_stop_fires_after_drive_seconds(self):
        hub = make_connected_hub()
        hub.drive("forward")
        self.assertNotIn(("stop",), hub._hub.motor_AB.calls)
        time.sleep(0.15)  # longer than drive_seconds=0.05
        self.assertIn(("stop",), hub._hub.motor_AB.calls)


if __name__ == "__main__":
    unittest.main()
