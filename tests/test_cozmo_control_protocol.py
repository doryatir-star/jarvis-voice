"""Byte-for-byte comparison of iphone-cozmo/cozmo_control.py's pure-stdlib
wire format against the pycozmo reference implementation. cozmo_control.py
has to be self-contained (no pip installs, so it runs inside on-device iOS
Python apps like Pythonista) — this test is what backs up the claim, in its
own docstring, that its bytes match a real, working Cozmo client. Skips if
pycozmo isn't installed (it's an optional dependency, only needed for
cozmo_hub.py and this test)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_control as cc

try:
    from pycozmo import protocol_encoder as pe
    from pycozmo import protocol_declaration as pd
    from pycozmo import lights as pl
    from pycozmo.frame import Frame
    _PYCOZMO_OK = True
except Exception:
    _PYCOZMO_OK = False


@unittest.skipUnless(_PYCOZMO_OK, "pycozmo isn't installed")
class TestWireFormatMatchesPycozmo(unittest.TestCase):
    def test_reset_frame(self):
        mine = cc.encode_frame(cc.FRAME_RESET, 0, 0, cc.OOB_SEQ)
        ref = Frame(pd.FrameType.RESET, 0, 0, pd.OOB_SEQ, []).to_bytes()
        self.assertEqual(mine, ref)

    def test_drive_wheels_frame(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 5, 5, 42, [cc.pkt_drive_wheels(123.5, -60.25, 1.0, 2.0)])
        ref = Frame(pd.FrameType.ENGINE, 5, 5, 42, [pe.DriveWheels(
            lwheel_speed_mmps=123.5, rwheel_speed_mmps=-60.25,
            lwheel_accel_mmps2=1.0, rwheel_accel_mmps2=2.0)]).to_bytes()
        self.assertEqual(mine, ref)

    def test_stop_all_motors_frame(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 7, 7, 3, [cc.pkt_stop_all_motors()])
        ref = Frame(pd.FrameType.ENGINE, 7, 7, 3, [pe.StopAllMotors()]).to_bytes()
        self.assertEqual(mine, ref)

    def test_set_head_angle_frame_matches_client_wrapper_defaults(self):
        # Client.set_head_angle() overrides SetHeadAngle's own internal
        # defaults (15.0/20.0) with 10.0/10.0 -- that's what must be matched.
        mine = cc.encode_frame(cc.FRAME_ENGINE, 1, 1, 0, [cc.pkt_set_head_angle(math.radians(30))])
        ref = Frame(pd.FrameType.ENGINE, 1, 1, 0, [pe.SetHeadAngle(
            angle_rad=math.radians(30), accel_rad_per_sec2=10.0, max_speed_rad_per_sec=10.0)]).to_bytes()
        self.assertEqual(mine, ref)

    def test_set_lift_height_frame_matches_client_wrapper_defaults(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 2, 2, 0, [cc.pkt_set_lift_height(80.0)])
        ref = Frame(pd.FrameType.ENGINE, 2, 2, 0, [pe.SetLiftHeight(
            height_mm=80.0, accel_rad_per_sec2=10.0, max_speed_rad_per_sec=10.0)]).to_bytes()
        self.assertEqual(mine, ref)

    def test_enable_frame(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 3, 3, 0, [cc.pkt_enable()])
        ref = Frame(pd.FrameType.ENGINE, 3, 3, 0, [pe.Enable()]).to_bytes()
        self.assertEqual(mine, ref)

    def test_set_origin_frame(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 4, 4, 0, [cc.pkt_set_origin()])
        ref = Frame(pd.FrameType.ENGINE, 4, 4, 0, [pe.SetOrigin()]).to_bytes()
        self.assertEqual(mine, ref)

    def test_sync_time_frame(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 6, 6, 0, [cc.pkt_sync_time()])
        ref = Frame(pd.FrameType.ENGINE, 6, 6, 0, [pe.SyncTime()]).to_bytes()
        self.assertEqual(mine, ref)

    def test_light_color_values(self):
        for name in ("green", "red", "blue", "white", "off"):
            self.assertEqual(cc.LIGHT_COLORS[name], getattr(pl, name).to_int16())

    def test_light_state_center_frame(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 8, 8, 0, [cc.pkt_light_center(cc.LIGHT_COLORS["green"])])
        ref = Frame(pd.FrameType.ENGINE, 8, 8, 0, [pe.LightStateCenter(
            states=(pl.green_light, pl.green_light, pl.green_light))]).to_bytes()
        self.assertEqual(mine, ref)

    def test_light_state_side_frame(self):
        mine = cc.encode_frame(cc.FRAME_ENGINE, 9, 9, 0, [cc.pkt_light_side(cc.LIGHT_COLORS["red"])])
        ref = Frame(pd.FrameType.ENGINE, 9, 9, 0, [pe.LightStateSide(
            states=(pl.red_light, pl.red_light))]).to_bytes()
        self.assertEqual(mine, ref)

    def test_ping_frame(self):
        mine = cc.encode_frame(cc.FRAME_PING, cc.OOB_SEQ, cc.OOB_SEQ, 12, ping_payload=cc.pkt_ping(1234.5, 7))
        ref = Frame(pd.FrameType.PING, pd.OOB_SEQ, pd.OOB_SEQ, 12,
                    [pe.Ping(time_sent_ms=1234.5, counter=7, last=0, unknown=0)]).to_bytes()
        self.assertEqual(mine, ref)

    def test_decode_handles_a_real_pycozmo_encoded_frame(self):
        body_pkt = pe.BodyInfo(serial_number=0xdeadbeef, body_hw_version=5, body_color=1)
        fw_pkt = pe.FirmwareSignature(unknown=99, signature="hello-firmware")
        raw = Frame(pd.FrameType.ENGINE, 0, 0, pd.OOB_SEQ, [fw_pkt, body_pkt]).to_bytes()

        decoded = cc.decode_frame(raw)
        self.assertIsNotNone(decoded)
        _, _, _, _, packets = decoded
        ids_seen = [pid for (_, pid, _) in packets]
        self.assertEqual(ids_seen, [cc.ID_FIRMWARE_SIGNATURE, cc.ID_BODY_INFO])

        _, _, fw_payload = packets[0]
        reencoded_fw = pe.FirmwareSignature.from_bytes(fw_payload)
        self.assertEqual((reencoded_fw.unknown, reencoded_fw.signature), (99, "hello-firmware"))

        _, _, body_payload = packets[1]
        reencoded_body = pe.BodyInfo.from_bytes(body_payload)
        self.assertEqual(
            (reencoded_body.serial_number, reencoded_body.body_hw_version, reencoded_body.body_color.value),
            (0xdeadbeef, 5, 1))


class FakeLink:
    def __init__(self):
        self.calls = []

    def drive(self, direction, **kw): self.calls.append(("drive", direction))
    def turn(self, direction, **kw): self.calls.append(("turn", direction))
    def stop(self): self.calls.append(("stop",))
    def head(self, direction): self.calls.append(("head", direction))
    def lift(self, direction): self.calls.append(("lift", direction))
    def lights(self, color): self.calls.append(("lights", color))


class TestCommandLanguage(unittest.TestCase):
    def test_every_command_dispatches_correctly(self):
        link = FakeLink()
        for cmd in ["forward", "backward", "left", "right", "stop",
                    "head up", "head down", "head center",
                    "lift up", "lift down", "lights blue"]:
            cc.handle_command(link, cmd)
        self.assertEqual(link.calls, [
            ("drive", "forward"), ("drive", "backward"),
            ("turn", "left"), ("turn", "right"),
            ("stop",),
            ("head", "up"), ("head", "down"), ("head", "center"),
            ("lift", "up"), ("lift", "down"),
            ("lights", "blue"),
        ])

    def test_unknown_command_does_not_crash(self):
        link = FakeLink()
        cc.handle_command(link, "asdkjfh")  # should print a hint, not raise
        self.assertEqual(link.calls, [])


if __name__ == "__main__":
    unittest.main()
