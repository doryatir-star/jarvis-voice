"""Tests for the face Cozmo shows on his own 128x32 screen.

The important one is TestEncoderMatchesReference: cozmo_all_in_one.py
reimplements pycozmo's display-image encoder in pure Python (pycozmo's
needs PIL and numpy, which no on-device Python app can install), so this
runs both against the same images and requires byte-for-byte identical
output. That check is skipped when pycozmo/PIL aren't installed; the rest
run anywhere.
"""
import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_all_in_one as app

try:
    from PIL import Image
    from pycozmo import image_encoder as ref_encoder
    _REF_OK = True
except Exception:
    _REF_OK = False


def _to_pil(bitmap):
    im = Image.new("1", (app.SCREEN_W, app.SCREEN_H))
    px = im.load()
    for x in range(app.SCREEN_W):
        for y in range(app.SCREEN_H):
            px[x, y] = 1 if bitmap.get(x, y) else 0
    return im


def _noise(density, seed):
    rng = random.Random(seed)
    bm = app.Bitmap()
    for x in range(app.SCREEN_W):
        for y in range(app.SCREEN_H):
            if rng.random() < density:
                bm.set(x, y)
    return bm


@unittest.skipUnless(_REF_OK, "pycozmo/PIL aren't installed")
class TestEncoderMatchesReference(unittest.TestCase):
    def _assert_matches(self, bitmap, label):
        mine = app.encode_display_image(bitmap)
        theirs = bytes(ref_encoder.ImageEncoder(_to_pil(bitmap)).encode())
        self.assertEqual(mine, theirs, f"encoding differs from pycozmo for {label}")

    def test_blank_and_full_screens(self):
        self._assert_matches(app.Bitmap(), "blank")
        full = app.Bitmap()
        for x in range(app.SCREEN_W):
            for y in range(app.SCREEN_H):
                full.set(x, y)
        self._assert_matches(full, "full")

    def test_noise_at_several_densities(self):
        # Different densities exercise different branches of the
        # run-length encoder: sparse hits the column-skip path, dense hits
        # the long-run path, middling hits neither.
        for density in (0.02, 0.1, 0.5, 0.9):
            self._assert_matches(_noise(density, seed=int(density * 1000)), f"noise {density}")

    def test_every_mood_encodes_identically(self):
        for mood in app.FACE_MOODS:
            self._assert_matches(app.render_face(mood), f"mood {mood}")

    def test_blinks_and_glances_encode_identically(self):
        for blink in (0.0, 0.3, 0.55, 0.95):
            self._assert_matches(app.render_face("neutral", blink=blink), f"blink {blink}")
        for look_x in (-10, -6, 0, 6, 10):
            self._assert_matches(app.render_face("happy", look_x=look_x), f"look {look_x}")

    def test_vertical_stripes(self):
        # Alternating columns are the worst case for the column repeat
        # and skip optimizations, which are the fiddliest part of the port.
        bm = app.Bitmap()
        for x in range(0, app.SCREEN_W, 3):
            for y in range(app.SCREEN_H):
                bm.set(x, y)
        self._assert_matches(bm, "stripes")


class TestFaceRendering(unittest.TestCase):
    def test_every_mood_lights_some_pixels_and_stays_on_screen(self):
        for mood in app.FACE_MOODS:
            bm = app.render_face(mood)
            self.assertGreater(sum(1 for b in bm.px if b), 50, f"{mood} drew almost nothing")
            self.assertEqual(len(bm.px), app.SCREEN_W * app.SCREEN_H)

    def test_a_full_blink_is_thinner_than_open_eyes(self):
        open_px = sum(1 for b in app.render_face("neutral", blink=0.0).px if b)
        shut_px = sum(1 for b in app.render_face("neutral", blink=0.95).px if b)
        self.assertLess(shut_px, open_px / 2)

    def test_glancing_moves_the_eyes_without_losing_them(self):
        centre = app.render_face("neutral")
        right = app.render_face("neutral", look_x=10)
        self.assertNotEqual(centre.px, right.px)
        self.assertGreater(sum(1 for b in right.px if b), 50)

    def test_unknown_mood_falls_back_to_neutral(self):
        self.assertEqual(app.render_face("ecstatic").px, app.render_face("neutral").px)


class TestDisplayPacket(unittest.TestCase):
    def test_packet_is_a_command_with_a_length_prefixed_payload(self):
        encoded = app.encode_display_image(app.render_face("happy"))
        pkt_type, pkt_id, payload = app.pkt_display_image(encoded)
        self.assertEqual(pkt_type, app.PT_COMMAND)
        self.assertEqual(pkt_id, 0x97)
        self.assertEqual(struct.unpack_from("<H", payload, 0)[0], len(encoded))
        self.assertEqual(payload[2:], encoded)


class TestMoodState(unittest.TestCase):
    def setUp(self):
        app.set_mood("neutral")

    def test_setting_a_mood_sticks(self):
        app.set_mood("excited")
        self.assertEqual(app.current_mood(), "excited")

    def test_an_unknown_mood_falls_back_instead_of_raising(self):
        app.set_mood("hangry")
        self.assertEqual(app.current_mood(), "neutral")

    def test_the_face_tool_changes_his_expression(self):
        class FakeLink:
            pass
        app.run_tool(FakeLink(), "face", {"mood": "surprised"})
        self.assertEqual(app.current_mood(), "surprised")


if __name__ == "__main__":
    unittest.main()
