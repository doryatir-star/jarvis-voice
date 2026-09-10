"""Tests for cozmo_control.py's camera support: the minigray_to_jpeg JPEG
reconstruction (checked byte-for-byte against pycozmo.camera, which needs
numpy -- skipped if unavailable) and CozmoLink's chunk reassembly (pure
Python, always runs)."""
import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_control as cc

try:
    from pycozmo import camera as ref_camera
    import numpy as np
    _REF_OK = True
except Exception:
    _REF_OK = False


@unittest.skipUnless(_REF_OK, "pycozmo/numpy aren't installed")
class TestMinigrayToJpegMatchesReference(unittest.TestCase):
    def test_matches_pycozmo_camera_module_byte_for_byte(self):
        random.seed(42)
        for _ in range(10):
            width, height = random.choice([(40, 30), (80, 60), (160, 120), (320, 240)])
            size = random.randint(50, 2000)
            data = bytes([0] + [random.randint(0, 255) for _ in range(size - 1)])

            mine = cc.minigray_to_jpeg(data, width, height)
            ref = ref_camera.minigray_to_jpeg(np.frombuffer(data, dtype=np.uint8), width, height)
            ref_bytes = bytes(ref.tolist())

            # pycozmo's version returns an over-allocated buffer with
            # trailing zero padding after the real JPEG content (harmless --
            # decoders stop at the end-of-image marker) -- this version
            # omits that padding, so compare the meaningful prefix and
            # confirm the "extra" reference bytes really are just padding.
            self.assertEqual(ref_bytes[:len(mine)], mine)
            self.assertTrue(all(b == 0 for b in ref_bytes[len(mine):]))
            self.assertEqual(mine[:2], b"\xff\xd8")
            self.assertEqual(mine[-2:], b"\xff\xd9")


def _chunk_payload(image_id, chunk_count, chunk_id, data, resolution=cc.DEFAULT_CAMERA_RESOLUTION):
    header = struct.pack("<LLLbbBBH", 0, image_id, 0, 0, resolution, chunk_count, chunk_id, 0)
    return header + struct.pack("<H", len(data)) + data


class TestImageChunkReassembly(unittest.TestCase):
    def setUp(self):
        self.link = cc.CozmoLink()
        self.link.ready = True

    def tearDown(self):
        self.link.sock.close()

    def test_out_of_order_chunks_reassemble_correctly(self):
        random.seed(7)
        full_data = bytes([0] + [random.randint(0, 255) for _ in range(300)])
        chunks = [full_data[0:101], full_data[101:201], full_data[201:301]]
        for chunk_id in (0, 2, 1):  # chunk 0 first, then out of order
            self.link._handle_packet(cc.PT_EVENT, cc.ID_IMAGE_CHUNK,
                                      _chunk_payload(42, len(chunks), chunk_id, chunks[chunk_id]))
        self.assertTrue(self.link._image_event.is_set())
        jpeg = self.link._latest_jpeg
        self.assertIsNotNone(jpeg)
        self.assertEqual(jpeg[:2], b"\xff\xd8")
        self.assertEqual(jpeg[-2:], b"\xff\xd9")

    def test_chunk_from_a_different_image_id_is_ignored(self):
        self.link._handle_packet(cc.PT_EVENT, cc.ID_IMAGE_CHUNK, _chunk_payload(1, 3, 0, b"a" * 50))
        self.link._image_event.clear()
        # A stray chunk claiming to belong to a different (never-started) image.
        self.link._handle_packet(cc.PT_EVENT, cc.ID_IMAGE_CHUNK, _chunk_payload(99, 3, 1, b"b" * 50))
        self.assertFalse(self.link._image_event.is_set())

    def test_new_image_starting_at_chunk_0_discards_any_incomplete_previous_one(self):
        self.link._handle_packet(cc.PT_EVENT, cc.ID_IMAGE_CHUNK, _chunk_payload(1, 3, 0, b"a" * 50))
        self.link._handle_packet(cc.PT_EVENT, cc.ID_IMAGE_CHUNK, _chunk_payload(1, 3, 1, b"b" * 50))
        # Never sent chunk 2 of image 1 -- now a brand new image starts.
        self.link._image_event.clear()
        full = bytes([0] + [1] * 30)
        self.link._handle_packet(cc.PT_EVENT, cc.ID_IMAGE_CHUNK, _chunk_payload(2, 1, 0, full))
        self.assertTrue(self.link._image_event.is_set())
        self.assertIsNotNone(self.link._latest_jpeg)


if __name__ == "__main__":
    unittest.main()
