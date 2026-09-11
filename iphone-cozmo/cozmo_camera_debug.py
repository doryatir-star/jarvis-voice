"""Standalone diagnostic for Cozmo's camera stream -- connects, enables the
camera, and prints exactly what happens: whether any image-chunk packets
arrive at all, and whether they assemble into a full frame. Run this on
its own (not through cozmo_web.py) to isolate a "camera feed is always
blank" problem from anything web-server-specific.

Usage: put this file next to cozmo_control.py and run it.
"""
import os
import sys
import time

try:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _THIS_DIR = os.getcwd()
sys.path.insert(0, _THIS_DIR)
import cozmo_control as cc

_chunk_events = []


def main():
    print("Connecting to Cozmo...")
    link = cc.CozmoLink()
    if not link.connect(timeout=8.0):
        print("Couldn't connect within 8 seconds. Check Wi-Fi/Cozmo is awake.")
        return

    # Patch in a print so we can see every single image-chunk packet that
    # arrives, before any reassembly/decoding happens -- this tells us
    # whether the problem is "no packets ever arrive" (network/protocol)
    # or "packets arrive but never assemble into a frame" (a bug in this
    # file's chunk handling).
    original = link._handle_image_chunk

    def logged_handle_image_chunk(payload):
        _chunk_events.append(time.time())
        print(f"  [chunk] received {len(payload)} bytes of raw packet data")
        original(payload)

    link._handle_image_chunk = logged_handle_image_chunk

    print("Connected. Enabling camera and waiting up to 10s per attempt for a frame...")
    for attempt in range(1, 6):
        before = len(_chunk_events)
        jpeg = link.capture_image(timeout=10.0)
        after = len(_chunk_events)
        chunks_this_attempt = after - before
        if jpeg:
            print(f"Attempt {attempt}: SUCCESS -- got a {len(jpeg)}-byte JPEG "
                  f"({chunks_this_attempt} raw chunk packets arrived).")
            with open("cozmo_debug_frame.jpg", "wb") as f:
                f.write(jpeg)
            print("Saved it as cozmo_debug_frame.jpg -- open that file to see what he saw.")
        elif chunks_this_attempt > 0:
            print(f"Attempt {attempt}: {chunks_this_attempt} raw chunk packets arrived, "
                  f"but never assembled into a complete frame in time.")
        else:
            print(f"Attempt {attempt}: NO packets arrived at all in 10 seconds.")

    print()
    print(f"Total raw image-chunk packets received across all attempts: {len(_chunk_events)}")
    if len(_chunk_events) == 0:
        print("Zero packets ever arrived -- this points to a network/firewall issue "
              "(something is blocking Cozmo's image-chunk packets from reaching this "
              "machine), not a bug in how the images get put together.")

    link.disconnect()
    print("Disconnected.")


if __name__ == "__main__":
    main()
