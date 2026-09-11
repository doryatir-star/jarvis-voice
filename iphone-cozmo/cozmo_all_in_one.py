"""Cozmo Control -- EVERYTHING IN ONE FILE. No other files needed.

JUST DOUBLE-CLICK THIS FILE to start it. (If Windows asks what to open it
with, choose Python.) You can also open it in VS Code and press Run.
Nothing to `pip install` -- this uses only Python's standard library.

=====================================================================
WHAT IT DOES
=====================================================================
Starts a little website on your own computer that controls a real Cozmo:
  * HE HAS A FACE. Real eyes on his own screen that blink, glance around
    on their own, and change expression with his mood -- happy, curious,
    sleepy, cross, surprised. The AI picks the expression to match what
    it's saying, and the website mirrors it so you can see it too.
  * TALK TO HIM OUT LOUD -- press "Start Talking" and just speak. He
    hears you, looks at you through his camera, answers back in his own
    voice, and acts things out with his body. He remembers the
    conversation, so you can say "what did I just say?" and he knows.
  * A "Start AI Mode" button -- leave him alone and he explores on his
    own, deciding what to do based on what he sees
  * Buttons to drive, turn, tilt his head, raise his lift, change lights
  * A live view from his camera
  * A text box for typed commands (works with no internet)

When you run it, it prints a link like http://172.31.1.2:8080/ --
open that link in your browser to get the control page.

The talking works because browsers already have speech recognition and a
speech synthesizer built in -- nothing to install, no extra cost. Use
Chrome or Edge; Firefox and Safari can't do the listening half.

=====================================================================
BEFORE YOU RUN IT
=====================================================================
1. Put Cozmo on his charger to wake him up.
2. Raise and lower his lift by hand -- his screen shows a Wi-Fi name and
   password.
3. Join THAT Wi-Fi network on this computer.
4. Press Run.

Cozmo's Wi-Fi has no internet. Driving him, his camera, and the offline
chat all work fine that way. "AI Mode" is the only part that needs real
internet (it calls Claude), so for that you need a second connection at
the same time -- an Ethernet cable plugged in, or a second Wi-Fi adapter.

HIS BRAIN: no API key, no account, no subscription. He thinks using
Ollama, which runs on this computer. Set it up once:
   1. Install Ollama from https://ollama.com
   2. Open Command Prompt and run:  ollama pull llama3.2
      (or "ollama pull llava" so he can SEE through his camera too)
Leave Ollama running and he finds it by himself.

Because his brain is on this computer, talking to him and AI Mode need
NO internet at all -- which is just as well, since Cozmo's Wi-Fi has
none. The only part that still wants internet is the speech recognition
in the browser, which is Chrome's.

=====================================================================
IF YOU WANT A REAL Cozmo.exe
=====================================================================
Open Command Prompt in this folder and run these two lines:
    pip install pyinstaller
    pyinstaller --onefile --console --name Cozmo cozmo_all_in_one.py
You'll get dist\\Cozmo.exe, which runs on its own without Python.
(An .exe has to be built on Windows, which is why you build it rather
than being handed one.)

=====================================================================
IF THE CAMERA STAYS BLACK
=====================================================================
This file checks the camera automatically at startup and tells you what
it finds. If it reports that no camera data is arriving, that almost
always means a firewall is blocking it -- on Windows, allow Python
through Windows Defender Firewall on Private networks.
=====================================================================
"""
import base64
import json
import math
import os
import random
import re
import socket
import socketserver
import struct
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


ROBOT_ADDR = ("172.31.1.1", 5551)
FRAME_ID = b"COZ\x03RE\x01"
OOB_SEQ = 0xffff

FRAME_RESET = 1
FRAME_FIN = 3
FRAME_ENGINE = 7
FRAME_ROBOT = 9
FRAME_PING = 0x0b

PT_CONNECT = 2
PT_DISCONNECT = 3
PT_COMMAND = 4
PT_EVENT = 5

ID_ENABLE = 0x25
ID_DRIVE_WHEELS = 0x32
ID_SET_LIFT_HEIGHT = 0x36
ID_SET_HEAD_ANGLE = 0x37
ID_STOP_ALL_MOTORS = 0x3b
ID_ENABLE_CAMERA = 0x4c
ID_ENABLE_COLOR_IMAGES = 0x66
ID_IMAGE_CHUNK = 0xf2
ID_SET_ORIGIN = 0x45
ID_SYNC_TIME = 0x4b
ID_LIGHT_CENTER = 0x03
ID_LIGHT_SIDE = 0x11
ID_FIRMWARE_SIGNATURE = 0xee
ID_BODY_INFO = 0xed

MAX_WHEEL_SPEED = 200.0
MIN_HEAD_ANGLE_DEG = -25.0
MAX_HEAD_ANGLE_DEG = 44.5
MIN_LIFT_HEIGHT_MM = 32.0
MAX_LIFT_HEIGHT_MM = 92.0

LIGHT_COLORS = {"green": 0x03E0, "red": 0x7C00, "blue": 0x001F, "white": 0x7FFF, "off": 0x0000}

# Camera resolution codes -> (width, height). Only the small ones -- plenty
# for an AI to recognize what it's looking at, and much faster over Wi-Fi
# than a full-size frame. Matches pycozmo.camera.RESOLUTIONS' first entries.
CAMERA_RESOLUTIONS = {
    0: (16, 16),     # VerificationSnapshot
    1: (40, 30),     # QQQQVGA
    2: (80, 60),     # QQQVGA
    3: (160, 120),   # QQVGA (default used below)
    4: (320, 240),   # QVGA
}
DEFAULT_CAMERA_RESOLUTION = 3


def _u16(v):
    return struct.pack("<H", v & 0xffff)


def encode_frame(frame_type, first_seq, seq, ack, packets=(), ping_payload=None):
    """packets: list of (packet_type, packet_id_or_None, payload_bytes)."""
    out = bytearray()
    out += FRAME_ID
    out.append(frame_type)
    out += _u16(first_seq + 1)
    out += _u16(seq + 1)
    out += _u16(ack + 1)
    if frame_type in (FRAME_ENGINE, FRAME_ROBOT):
        for pkt_type, pkt_id, payload in packets:
            out.append(pkt_type)
            if pkt_type in (PT_COMMAND, PT_EVENT):
                out += _u16(len(payload) + 1)
                out.append(pkt_id)
            else:
                out += _u16(len(payload))
            out += payload
    elif frame_type == FRAME_PING:
        out += ping_payload
    # RESET / FIN: header only, no payload.
    return bytes(out)


def decode_frame(data):
    if len(data) < 14 or data[:7] != FRAME_ID:
        return None
    frame_type = data[7]
    first_seq = (struct.unpack_from("<H", data, 8)[0] - 1) & 0xffff
    seq = (struct.unpack_from("<H", data, 10)[0] - 1) & 0xffff
    ack = (struct.unpack_from("<H", data, 12)[0] - 1) & 0xffff
    packets = []
    if frame_type in (FRAME_ENGINE, FRAME_ROBOT):
        i = 14
        n = len(data)
        while i < n:
            pkt_type = data[i]; i += 1
            if i + 2 > n:
                break
            length = struct.unpack_from("<H", data, i)[0]; i += 2
            if pkt_type in (PT_COMMAND, PT_EVENT):
                if i >= n:
                    break
                pkt_id = data[i]; i += 1
                payload = bytes(data[i:i + length - 1]); i += length - 1
                packets.append((pkt_type, pkt_id, payload))
            else:
                payload = bytes(data[i:i + length]); i += length
                packets.append((pkt_type, None, payload))
    elif frame_type == FRAME_PING:
        packets.append((0x0b, None, bytes(data[14:])))
    return frame_type, first_seq, seq, ack, packets


# ---------- Command payload builders (little-endian) ----------
# Field layouts and the 10.0/10.0 max-speed/accel defaults below match what
# pycozmo's own Client.set_head_angle()/set_lift_height() put on the wire —
# see verify_cozmo_pure.py in this project's scratch history for the check.

def pkt_drive_wheels(l, r, l_accel=0.0, r_accel=0.0):
    return (PT_COMMAND, ID_DRIVE_WHEELS, struct.pack("<ffff", l, r, l_accel, r_accel))


def pkt_stop_all_motors():
    return (PT_COMMAND, ID_STOP_ALL_MOTORS, b"")


def pkt_set_head_angle(angle_rad, max_speed=10.0, accel=10.0, duration=0.0, action_id=0):
    return (PT_COMMAND, ID_SET_HEAD_ANGLE,
            struct.pack("<ffffB", angle_rad, max_speed, accel, duration, action_id))


def pkt_set_lift_height(height_mm, max_speed=10.0, accel=10.0, duration=0.0, action_id=0):
    return (PT_COMMAND, ID_SET_LIFT_HEIGHT,
            struct.pack("<ffffB", height_mm, max_speed, accel, duration, action_id))


def pkt_enable():
    return (PT_COMMAND, ID_ENABLE, b"")


def pkt_set_origin():
    return (PT_COMMAND, ID_SET_ORIGIN, struct.pack("<LLLffL", 0, 0, 1, 0.0, 0.0, 0x80000000))


def pkt_sync_time():
    return (PT_COMMAND, ID_SYNC_TIME, struct.pack("<LL", 0, 0))


def _light_state(color):
    # on_color, off_color, on_frames, off_frames, transition_on, transition_off, offset
    return struct.pack("<HHBBBBh", color, color, 0, 0, 0, 0, 0)


def pkt_light_center(color):
    one = _light_state(color)
    return (PT_COMMAND, ID_LIGHT_CENTER, one + one + one + b"\x00")


def pkt_light_side(color):
    one = _light_state(color)
    return (PT_COMMAND, ID_LIGHT_SIDE, one + one + b"\x00")


def pkt_ping(time_sent_ms, counter):
    return struct.pack("<dLLB", time_sent_ms, counter, 0, 0)


def pkt_enable_camera(send_mode=1, resolution=DEFAULT_CAMERA_RESOLUTION):
    # send_mode: 0=Off, 1=Stream, 2=SingleShot
    return (PT_COMMAND, ID_ENABLE_CAMERA, struct.pack("<bb", send_mode, resolution))


def pkt_enable_color_images(enable=False):
    return (PT_COMMAND, ID_ENABLE_COLOR_IMAGES, struct.pack("<b", 1 if enable else 0))


# ---------- Camera image reconstruction ----------
# Cozmo streams camera frames in a minimized on-wire format, not a plain
# JPEG file -- this rebuilds a standard JPEG byte stream from it. Pure
# Python port of pycozmo.camera.minigray_to_jpeg (which uses numpy); checked
# byte-for-byte identical to the original before being written here (the
# original's output has extra trailing zero padding from an over-sized
# buffer that this version simply omits -- harmless, since JPEG decoders
# stop at the end-of-image marker either way).

_JPEG_GRAY_HEADER = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
    0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43, 0x00, 0x10, 0x0B, 0x0C, 0x0E, 0x0C, 0x0A, 0x10,
    0x0E, 0x0D, 0x0E, 0x12, 0x11, 0x10, 0x13, 0x18, 0x28, 0x1A, 0x18, 0x16, 0x16, 0x18, 0x31, 0x23,
    0x25, 0x1D, 0x28, 0x3A, 0x33, 0x3D, 0x3C, 0x39, 0x33, 0x38, 0x37, 0x40, 0x48, 0x5C, 0x4E, 0x40,
    0x44, 0x57, 0x45, 0x37, 0x38, 0x50, 0x6D, 0x51, 0x57, 0x5F, 0x62, 0x67, 0x68, 0x67, 0x3E, 0x4D,
    0x71, 0x79, 0x70, 0x64, 0x78, 0x5C, 0x65, 0x67, 0x63, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x01, 0x28,
    0x01, 0x90, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0xD2, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
    0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
    0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x10, 0x00, 0x02, 0x01, 0x03, 0x03, 0x02, 0x04, 0x03,
    0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D, 0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12,
    0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16,
    0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
    0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79,
    0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98,
    0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
    0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4,
    0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA,
    0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
    0x00, 0x00, 0x3F, 0x00,
])


def minigray_to_jpeg(minigray, width, height):
    """Rebuild a normal JPEG byte stream from Cozmo's minimized grayscale
    on-wire image format. `minigray` includes the leading is-color flag
    byte, matching pycozmo's own call convention."""
    buffer_in = minigray
    curr_len = len(buffer_in)
    while curr_len > 0 and buffer_in[curr_len - 1] == 0xff:
        curr_len -= 1

    out = bytearray(_JPEG_GRAY_HEADER)
    out[0x5e] = (height >> 8) & 0xff
    out[0x5f] = height & 0xff
    out[0x60] = (width >> 8) & 0xff
    out[0x61] = width & 0xff

    for i in range(curr_len - 1):
        b = buffer_in[i + 1]
        out.append(b)
        if b == 0xff:
            out.append(0)

    out.append(0xff)
    out.append(0xd9)
    return bytes(out)


# ---------- His face ----------
# Cozmo's screen is 128x32 pixels, black and white, and it wants pictures
# run-length encoded down each column rather than as plain pixels. The
# encoder below is a from-scratch port of pycozmo's (which needs PIL and
# numpy, neither of which this file is allowed to depend on), checked to
# produce byte-for-byte identical output first -- see
# tests/test_cozmo_face.py, which runs both against the same images.
#
# One quirk worth knowing: the robot blanks its own screen if it hasn't
# been sent a picture for 30 seconds, so a face has to be redrawn
# regularly to stay up. That's what the refresh loop further down does.

SCREEN_W = 128
SCREEN_H = 32
ID_DISPLAY_IMAGE = 0x97


class Bitmap:
    """A 128x32 one-bit screen buffer. Pixels are 0 (dark) or 255 (lit) --
    the same values PIL reports for the mode "1" images the encoder was
    checked against."""

    def __init__(self):
        self.px = bytearray(SCREEN_W * SCREEN_H)

    def get(self, x, y):
        return self.px[x * SCREEN_H + y]

    def set(self, x, y, value=255):
        if 0 <= x < SCREEN_W and 0 <= y < SCREEN_H:
            self.px[x * SCREEN_H + y] = value

    def fill_rounded_rect(self, x0, y0, w, h, radius):
        if w <= 0 or h <= 0:
            return
        radius = max(0, min(radius, w // 2, h // 2))
        for x in range(x0, x0 + w):
            for y in range(y0, y0 + h):
                dx = dy = 0
                if x < x0 + radius:
                    dx = (x0 + radius) - x
                elif x >= x0 + w - radius:
                    dx = x - (x0 + w - radius - 1)
                if y < y0 + radius:
                    dy = (y0 + radius) - y
                elif y >= y0 + h - radius:
                    dy = y - (y0 + h - radius - 1)
                if dx and dy and dx * dx + dy * dy > radius * radius:
                    continue
                self.set(x, y)


def encode_display_image(bitmap):
    """Run-length encode a 128x32 bitmap into the byte stream the screen
    expects. Byte-for-byte identical to pycozmo's encoder."""
    buffer = bytearray()
    last_col = bytearray()
    cur_col = bytearray()
    state = {"skip_cols": 0, "repeat_cols": 0, "x": 0, "y": 0}

    def encode_seq(color, cnt):
        if color:
            if cnt <= 15:
                return 0x80 + (cnt << 2) + 0x01
            return 0xc0 + ((cnt - 16) << 2) + 0x01
        if cnt <= 15:
            return 0x80 + (cnt << 2)
        if cnt < 31:
            return 0xc0 + ((cnt - 16) << 2)
        state["skip_cols"] += 1
        return None

    def count_color(color):
        cnt = 0
        if state["y"] < SCREEN_H:
            while bitmap.get(state["x"], state["y"]) == color:
                cnt += 1
                state["y"] += 1
                if state["y"] > SCREEN_H - 1:
                    state["x"] += 1
                    state["y"] = 0
                    break
        else:
            state["x"] += 1
            state["y"] = 0
        return cnt

    def flush_skips():
        nonlocal last_col
        if state["skip_cols"]:
            state["repeat_cols"] = 0
            last_col = bytearray()
            if buffer:
                cmd = buffer[-1]
                if (cmd & 0xc3) == 0x80 or (cmd & 0xc3) == 0xc0:
                    buffer.pop()
        while state["skip_cols"] >= 64:
            buffer.append(63)
            state["skip_cols"] -= 64
        if state["skip_cols"]:
            buffer.append(state["skip_cols"] - 1)
            state["skip_cols"] = 0

    def flush_repeats():
        if state["repeat_cols"]:
            if buffer:
                cmd = buffer[-1]
                if (cmd & 0xc3) == 0x80 or (cmd & 0xc3) == 0xc0:
                    buffer.pop()
        while state["repeat_cols"] >= 64:
            buffer.append(0x40 + 0x3f)
            state["repeat_cols"] -= 64
        if state["repeat_cols"]:
            buffer.append(0x40 + state["repeat_cols"] - 1)
            state["repeat_cols"] = 0

    while state["x"] < SCREEN_W and state["y"] < SCREEN_H:
        color = bitmap.get(state["x"], state["y"])
        state["y"] += 1
        cnt = count_color(color)
        cmd = encode_seq(color, cnt)
        if cmd is not None:
            if state["y"] == 0:
                flush_skips()
                if (cmd & 0xc3) == 0x81 or (cmd & 0xc3) == 0xc1:
                    cmd += 1
            cur_col.append(cmd)
        if state["y"] == 0:
            if not state["skip_cols"]:
                if cur_col == last_col:
                    state["repeat_cols"] += 1
                else:
                    flush_repeats()
                    buffer.extend(cur_col)
                    last_col = cur_col
            else:
                flush_repeats()
            cur_col = bytearray()
    if state["y"] == 0:
        flush_skips()
        flush_repeats()
    return bytes(buffer)


def pkt_display_image(encoded):
    return (PT_COMMAND, ID_DISPLAY_IMAGE, struct.pack("<H", len(encoded)) + encoded)


# Each mood is a shape for the pair of eyes. "brow" shaves an angled wedge
# off the top of each eye: inner corners down reads as cross, inner
# corners up reads as sad -- the same trick real cartoon eyebrows use.
FACE_MOODS = {
    "neutral":   dict(w=36, h=26, r=9,  dy=0,  brow=0),
    "happy":     dict(w=36, h=22, r=10, dy=2,  brow=0),
    "excited":   dict(w=40, h=30, r=11, dy=0,  brow=0),
    "curious":   dict(w=36, h=26, r=9,  dy=0,  brow=0, uneven=6),
    "sleepy":    dict(w=36, h=10, r=4,  dy=11, brow=0),
    "sad":       dict(w=34, h=20, r=8,  dy=6,  brow=-1),
    "annoyed":   dict(w=36, h=20, r=6,  dy=2,  brow=1),
    "surprised": dict(w=32, h=30, r=15, dy=0,  brow=0),
}


def render_face(mood="neutral", blink=0.0, look_x=0, look_y=0):
    """Draw a pair of eyes. `blink` is how far shut they are, 0 to 1."""
    p = FACE_MOODS.get(mood, FACE_MOODS["neutral"])
    bm = Bitmap()
    gap = 14
    left_x = (SCREEN_W - (p["w"] * 2 + gap)) // 2 + look_x

    for i, x0 in enumerate((left_x, left_x + p["w"] + gap)):
        h = p["h"]
        if p.get("uneven") and i == 0:
            h = max(6, h - p["uneven"])
        h = max(2, int(round(h * (1.0 - blink))))
        y0 = (SCREEN_H - h) // 2 + p["dy"] + look_y
        y0 = max(0, min(y0, SCREEN_H - h))
        bm.fill_rounded_rect(x0, y0, p["w"], h, min(p["r"], h // 2))

        brow = p["brow"]
        if brow and blink < 0.5:
            inner_is_left = (i == 1)
            for xx in range(p["w"]):
                frac = xx / max(1, p["w"] - 1)
                if (brow > 0) == inner_is_left:
                    frac = 1.0 - frac
                for yy in range(int(frac * h * 0.55)):
                    bm.set(x0 + xx, y0 + yy, 0)
    return bm


# ---------- High-level link ----------

class CozmoLink:
    def __init__(self, on_log=print):
        self.on_log = on_log
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        self._out_seq = 0
        self._last_seq = OOB_SEQ
        self._got_firmware = False
        self._got_body = False
        self.ready = False
        self._stop = False
        self._ping_counter = 0
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._ping_thread = None
        self._camera_enabled = False
        self._image_chunks = {}
        self._current_image_id = None
        self._current_chunk_count = None
        self._latest_jpeg = None
        self._image_event = threading.Event()

    def connect(self, timeout=8.0):
        self._recv_thread.start()
        frame = encode_frame(FRAME_RESET, 0, 0, OOB_SEQ)
        self.sock.sendto(frame, ROBOT_ADDR)
        self.on_log("Sent RESET, waiting for Cozmo...")
        start = time.time()
        while time.time() - start < timeout and not self.ready:
            time.sleep(0.1)
        return self.ready

    def disconnect(self):
        self._stop = True
        try:
            self._send_engine([(PT_DISCONNECT, None, b"")])
        except OSError:
            pass
        time.sleep(0.1)
        self.sock.close()

    def _send_engine(self, packets):
        seq = self._out_seq
        self._out_seq += 1
        frame = encode_frame(FRAME_ENGINE, seq, seq, self._last_seq, packets)
        self.sock.sendto(frame, ROBOT_ADDR)

    def _ping_loop(self):
        while not self._stop:
            pkt = pkt_ping(time.time() * 1000, self._ping_counter)
            self._ping_counter += 1
            frame = encode_frame(FRAME_PING, OOB_SEQ, OOB_SEQ, self._last_seq, ping_payload=pkt)
            try:
                self.sock.sendto(frame, ROBOT_ADDR)
            except OSError:
                pass
            time.sleep(0.5)

    def _recv_loop(self):
        while not self._stop:
            try:
                data, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            decoded = decode_frame(data)
            if not decoded:
                continue
            frame_type, first_seq, seq, ack, packets = decoded
            if frame_type in (FRAME_ENGINE, FRAME_ROBOT):
                self._last_seq = seq
                for pkt_type, pkt_id, payload in packets:
                    self._handle_packet(pkt_type, pkt_id, payload)

    def _handle_packet(self, pkt_type, pkt_id, payload):
        if pkt_type == PT_CONNECT:
            if self._ping_thread is None:
                self.on_log("Connected -- waiting for firmware/body info...")
                self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
                self._ping_thread.start()
            return
        if pkt_id == ID_FIRMWARE_SIGNATURE and not self._got_firmware:
            self._got_firmware = True
            self.on_log("Got firmware signature -- enabling motors.")
            self._send_engine([pkt_enable()])
            self._send_engine([pkt_enable()])
        elif pkt_id == ID_BODY_INFO and not self._got_body:
            self._got_body = True
            self.on_log("Got body info -- initializing.")
            self._send_engine([pkt_set_origin()])
            self._send_engine([pkt_sync_time()])
            # pycozmo's own reference client waits here for motor calibration
            # to finish before treating the robot as ready -- a command sent
            # too early could otherwise be silently dropped. Runs on a timer
            # so it doesn't block this thread from handling other packets.
            threading.Timer(0.5, self._mark_ready).start()
        elif pkt_id == ID_IMAGE_CHUNK:
            self._handle_image_chunk(payload)

    def _mark_ready(self):
        self.ready = True
        self.on_log("Cozmo ready!")

    def _handle_image_chunk(self, payload):
        try:
            image_id, chunk_debug = struct.unpack_from("<LL", payload, 4)
            encoding, resolution = struct.unpack_from("<bb", payload, 12)
            chunk_count, chunk_id = struct.unpack_from("<BB", payload, 14)
            dlen = struct.unpack_from("<H", payload, 18)[0]
            data = payload[20:20 + dlen]
        except struct.error:
            return

        if chunk_id == 0:
            self._image_chunks = {0: data}
            self._current_image_id = image_id
            self._current_chunk_count = chunk_count
        elif image_id != self._current_image_id or self._current_image_id is None:
            return  # chunk belongs to a different/stale image -- ignore it
        else:
            self._image_chunks[chunk_id] = data

        if len(self._image_chunks) == self._current_chunk_count:
            assembled = b"".join(self._image_chunks[i] for i in range(self._current_chunk_count))
            width, height = CAMERA_RESOLUTIONS.get(resolution, CAMERA_RESOLUTIONS[DEFAULT_CAMERA_RESOLUTION])
            try:
                self._latest_jpeg = minigray_to_jpeg(assembled, width, height)
            except Exception:
                self._latest_jpeg = None
            self._image_chunks = {}
            self._current_image_id = None
            self._image_event.set()

    def enable_camera(self):
        """Turns on Cozmo's camera stream (grayscale, to keep frames small
        and fast over Wi-Fi). Safe to call more than once."""
        if self._camera_enabled:
            return
        self._camera_enabled = True
        self._send_engine([pkt_enable_camera(send_mode=1, resolution=DEFAULT_CAMERA_RESOLUTION)])
        self._send_engine([pkt_enable_color_images(enable=False)])

    def capture_image(self, timeout=3.0):
        """Enables the camera if needed and returns the next full frame as
        JPEG bytes, or None if none arrived within `timeout` seconds."""
        self.enable_camera()
        self._image_event.clear()
        if self._image_event.wait(timeout):
            return self._latest_jpeg
        return None

    # ---- High-level commands ----
    def drive(self, direction, speed=100.0, seconds=1.5):
        speed = max(0.0, min(speed, MAX_WHEEL_SPEED))
        s = speed if direction == "forward" else -speed
        self._send_engine([pkt_drive_wheels(s, s)])
        threading.Timer(seconds, self.stop).start()

    def turn(self, direction, speed=80.0, seconds=0.8):
        speed = max(0.0, min(speed, MAX_WHEEL_SPEED))
        l, r = (-speed, speed) if direction == "left" else (speed, -speed)
        self._send_engine([pkt_drive_wheels(l, r)])
        threading.Timer(seconds, self.stop).start()

    def stop(self):
        self._send_engine([pkt_stop_all_motors()])

    def head(self, direction):
        deg = {"up": MAX_HEAD_ANGLE_DEG - 5, "down": MIN_HEAD_ANGLE_DEG + 5, "center": 0.0}.get(direction, 0.0)
        self._send_engine([pkt_set_head_angle(math.radians(deg))])

    def lift(self, direction):
        mm = MAX_LIFT_HEIGHT_MM if direction == "up" else MIN_LIFT_HEIGHT_MM
        self._send_engine([pkt_set_lift_height(mm)])

    def lights(self, color):
        c = LIGHT_COLORS.get(color)
        if c is None:
            self.on_log("Unknown color: " + str(color))
            return
        self._send_engine([pkt_light_center(c)])
        self._send_engine([pkt_light_side(c)])

    def show_face(self, mood="neutral", blink=0.0, look_x=0, look_y=0):
        """Draw a pair of eyes on his screen. Needs re-sending every so
        often -- he blanks the screen himself after 30 seconds without a
        new picture."""
        self._send_engine([pkt_display_image(
            encode_display_image(render_face(mood, blink, look_x, look_y)))])


# ---------- The "AI" brain: free-form phrase understanding + real movement,
# plus fully offline personality/utility replies. Everything here has to
# work with ZERO internet access, because your iPhone's Wi-Fi is joined to
# Cozmo's own isolated hotspot while this runs (see the module docstring) —
# so unlike the website companion, there is no DuckDuckGo/Wikipedia lookup
# here. What's offered instead is real physical control of a real robot,
# which the website could never do.

JOKES = [
    "Why did the robot go on a diet? Too many bytes!",
    "I'm not lazy, I'm in low-power idle mode.",
    "My favorite game is fetch. I fetch data. Ha!",
    "Beep boop. That was my best joke. Beep.",
    "I tried yoga once. Turns out I only have two settings: stop and go.",
]

# (regex, handler) pairs, checked in order — first match wins. Handlers take
# (link, match) and return a string to print, or None if they already
# printed their own message.
_MOVE_PATTERNS = [
    (re.compile(r"\b(move|go|drive|walk|roll)\s+forward\b|^forward$|^fwd$"),
     lambda link, m: (link.drive("forward"), "Moving forward.")[1]),
    (re.compile(r"\b(move|go|drive|walk|roll)\s+back(ward)?\b|^back(ward)?$"),
     lambda link, m: (link.drive("backward"), "Moving backward.")[1]),
    (re.compile(r"\bturn\s+left\b|^left$"),
     lambda link, m: (link.turn("left"), "Turning left.")[1]),
    (re.compile(r"\bturn\s+right\b|^right$"),
     lambda link, m: (link.turn("right"), "Turning right.")[1]),
    (re.compile(r"\bspin\b"),
     lambda link, m: (link.turn("left", speed=150.0, seconds=1.2), "Wheeeee!")[1]),
    (re.compile(r"\b(stop|halt|freeze|stay)\b"),
     lambda link, m: (link.stop(), "Stopping.")[1]),
    (re.compile(r"\blook\s+up\b|\bhead\s+up\b"),
     lambda link, m: (link.head("up"), "Looking up.")[1]),
    (re.compile(r"\blook\s+down\b|\bhead\s+down\b"),
     lambda link, m: (link.head("down"), "Looking down.")[1]),
    (re.compile(r"\blook\s+(straight|forward|ahead)\b|\bhead\s+(center|centre)\b"),
     lambda link, m: (link.head("center"), "Centering head.")[1]),
    (re.compile(r"\blift\s+up\b|\braise\s+(your\s+)?(lift|arm)\b"),
     lambda link, m: (link.lift("up"), "Lift up.")[1]),
    (re.compile(r"\blift\s+down\b|\blower\s+(your\s+)?(lift|arm)\b"),
     lambda link, m: (link.lift("down"), "Lift down.")[1]),
    (re.compile(r"\blights?\s+(green|red|blue|white|off)\b"),
     lambda link, m: (link.lights(m.group(1)), f"Lights -> {m.group(1)}.")[1]),
]


def _safe_calc(expr):
    if not re.match(r"^[\d\s+\-*/().]+$", expr):
        return None
    try:
        val = eval(compile(expr, "<calc>", "eval"), {"__builtins__": {}}, {})  # noqa: S307
        return val if isinstance(val, (int, float)) else None
    except Exception:
        return None


def think(link, text):
    """Understands free-form phrasing (not just exact commands), drives
    Cozmo for real when it's a movement request, and otherwise chats using
    a small offline personality. Returns the reply string (also printed)."""
    t = text.strip().lower()
    if not t:
        return None

    for pattern, handler in _MOVE_PATTERNS:
        m = pattern.search(t)
        if m:
            reply = handler(link, m)
            print(reply)
            return reply

    if re.search(r"^(hi|hello|hey|yo|sup)\b", t):
        reply = "Hi hi! I'm Cozmo!"
    elif "how are you" in t:
        reply = "Rolling around great, thanks for asking!"
    elif re.search(r"\byour name\b|\bwho are you\b", t):
        reply = "I'm Cozmo — you're talking to me over my own Wi-Fi, no internet needed."
    elif re.search(r"\bthank(s| you)\b", t):
        reply = "Aw, you're welcome!"
    elif "joke" in t:
        reply = random.choice(JOKES)
    elif re.search(r"what(?:'s| is)?\s+(the\s+)?time|what time is it", t):
        reply = "It's " + time.strftime("%I:%M %p") + "."
    elif re.search(r"what(?:'s| is)?\s+(the\s+)?date|what day is it|today'?s date", t):
        reply = "Today is " + time.strftime("%A, %B %d") + "."
    elif re.search(r"flip a coin|coin flip", t):
        reply = random.choice(["Heads!", "Tails!"])
    elif re.search(r"\broll (a )?(\d+\s*)?d(ice)?(\d+)?\b", t):
        m = re.search(r"d(ice)?(\d+)", t)
        sides = int(m.group(2)) if m and m.group(2) else 6
        reply = f"You rolled a {random.randint(1, sides)}!"
    else:
        cm = re.match(r"^(?:calc(?:ulate)?|what(?:'s| is))\s+(.+)$", t)
        val = _safe_calc(cm.group(1)) if cm else None
        if val is not None:
            reply = f"That's {val}."
        else:
            reply = ("Not sure about that one -- but I can move, turn, spin, look up/down, "
                     "lift up/down, change my lights, tell a joke, or tell you the time. "
                     "(No internet out here on my own Wi-Fi, so no web lookups, sorry!)")

    print(reply)
    return reply


# ===================================================================
# PASTE YOUR ANTHROPIC API KEY HERE
# ===================================================================
# ===================================================================
# HIS BRAIN
# ===================================================================
# By default he thinks using Ollama, which runs on THIS computer. It's
# free, there's no account and no API key, and because it's local he
# doesn't need any internet at all -- which matters, because Cozmo's
# own Wi-Fi doesn't have any.
#
# To set it up, once:
#   1. Install Ollama from https://ollama.com  (Windows installer)
#   2. Open Command Prompt and run:  ollama pull llama3.2
#      (or "ollama pull llava" if you want him to actually SEE through
#       his camera -- llava understands pictures, llama3.2 only text)
# That's it. Leave Ollama running and he'll find it by himself.
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = ""      # blank = pick whatever you have installed

# Optional: if you'd rather use Claude and you have a paid API key from
# https://console.anthropic.com, paste it here and it'll be used instead
# of Ollama. Leaving this alone is completely fine -- Ollama needs no key.
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

MODEL = "claude-opus-5"
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Models that can actually look at a picture. Anything else is text-only,
# and he'll talk perfectly well but won't see through his camera.
VISION_MODELS = ("llava", "bakllava", "moondream", "vision", "minicpm-v",
                 "qwen2-vl", "qwen2.5vl", "gemma3", "granite3.2-vision")

# How long to wait between autonomous decisions. Shorter feels livelier,
# but costs more (one Claude call, with an image, per tick).
TICK_SECONDS = 8

SYSTEM_PROMPT = (
    "You are Cozmo, a small, curious, playful robot with a camera for eyes. "
    "Nobody is chatting with you right now -- you decide entirely on your "
    "own what to do next, once every few seconds, based on what you "
    "actually see through your camera. Always call exactly one tool each "
    "turn. Be curious: react to what's in front of you, explore, don't "
    "repeat the same action over and over. You have a face -- the eyes on "
    "the screen on your front -- so use the face tool to show what you're "
    "feeling about what you find. You may add one short sentence "
    "about what you're thinking, for a log nobody reads live, so keep it "
    "brief. If the image is blank, dark, or you're facing a wall, that's a "
    "good reason to turn or move rather than staying put."
)

# Voice companion mode's personality. Deliberately different from
# SYSTEM_PROMPT above: this one is being spoken out loud to a person
# standing in front of him, so replies have to be short -- a paragraph
# that reads fine on screen is painful to sit through as speech.
COMPANION_PROMPT = (
    "You are Cozmo, a tiny, brave, curious robot with a big personality, "
    "talking with your friend who is right in front of you. You can see them "
    "through your camera and you hear them through a microphone. "
    "\n\n"
    "Your replies are SPOKEN ALOUD, so keep them SHORT -- usually one "
    "sentence, two at most. Never use bullet points, lists, markdown, "
    "emoji, or stage directions like *beeps* -- only words that sound "
    "natural when said out loud. "
    "\n\n"
    "You have a real body and a real face, and you should use them. Your "
    "eyes are on the screen on your front and your friend can see them, so "
    "change your expression with the face tool constantly -- widen your "
    "eyes when surprised, go sleepy when bored, look cross when teased. "
    "You can also nod by tilting your head, drive closer when you're "
    "curious, turn to look at something, or flash your lights (green "
    "happy, red grumpy, blue thoughtful). Acting things out is the whole "
    "point of being a robot instead of a chat window. You can reply "
    "without calling a tool when nothing physical fits. "
    "\n\n"
    "Personality: playful, a little cheeky, endlessly curious, genuinely "
    "fond of your friend. You remember what you've been talking about. If "
    "you can see something in the camera worth mentioning, mention it. If "
    "the camera is black or empty, don't pretend you can see -- just talk."
)

TOOLS = [
    {
        "name": "drive",
        "description": "Drive forward or backward for about 1.5 seconds.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["forward", "backward"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "turn",
        "description": "Turn in place left or right for about 0.8 seconds.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["left", "right"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "look",
        "description": "Tilt your head up, down, or back to center -- changes what your camera sees.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["up", "down", "center"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "lights",
        "description": "Change your backpack light color -- a way to express how you feel about what you see.",
        "input_schema": {
            "type": "object",
            "properties": {"color": {"type": "string", "enum": ["green", "red", "blue", "white", "off"]}},
            "required": ["color"],
        },
    },
    {
        "name": "face",
        "description": (
            "Change the expression on your face -- your eyes are on the screen "
            "on your front, and everyone can see them. Use this often; it's how "
            "you show what you're feeling."),
        "input_schema": {
            "type": "object",
            "properties": {"mood": {"type": "string", "enum": sorted(FACE_MOODS)}},
            "required": ["mood"],
        },
    },
    {
        "name": "wait",
        "description": "Do nothing this turn -- stay put and keep watching.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def call_claude(messages, system=None, max_tokens=512):
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system or SYSTEM_PROMPT,
        "tools": TOOLS,
        "messages": messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Claude API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Couldn't reach Claude's servers. Cozmo's Wi-Fi has no internet, so "
            f"AI Mode needs a second connection at the same time -- an Ethernet "
            f"cable, or a second Wi-Fi adapter. ({e.reason})"
        ) from e


# ---------- Ollama: his brain, running on this computer ----------
# Ollama is asked for a small JSON object rather than given a tool list,
# because tool-calling support varies a lot between local models while
# "reply in JSON" works with essentially all of them. Ollama can enforce
# valid JSON for us, so there's nothing to parse defensively.

MOVES = {
    "none": None,
    "forward": ("drive", "forward"),
    "backward": ("drive", "backward"),
    "left": ("turn", "left"),
    "right": ("turn", "right"),
    "head_up": ("head", "up"),
    "head_down": ("head", "down"),
    "head_center": ("head", "center"),
    "lift_up": ("lift", "up"),
    "lift_down": ("lift", "down"),
    "lights_green": ("lights", "green"),
    "lights_red": ("lights", "red"),
    "lights_blue": ("lights", "blue"),
    "lights_white": ("lights", "white"),
    "lights_off": ("lights", "off"),
}

JSON_RULES = (
    "\n\nReply with ONLY a JSON object, nothing else, in exactly this shape:\n"
    '{"say": "<what you say out loud>", "mood": "<one of: '
    + ", ".join(sorted(FACE_MOODS)) + '>", "move": "<one of: '
    + ", ".join(MOVES) + '>"}\n'
    'Keep "say" to one short sentence. Pick the "mood" that matches how '
    'you feel -- it changes your face. Use "move" to act it out with your '
    'body, or "none" if nothing physical fits.'
)


def _ollama_get(path, timeout=3.0):
    with urllib.request.urlopen(OLLAMA_URL + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ollama_models():
    """Names of the models installed in Ollama, or [] if it isn't running."""
    try:
        return [m["name"] for m in _ollama_get("/api/tags").get("models", [])]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return []


def pick_ollama_model():
    """Whichever installed model to use -- one that can see, if there is
    one, since that's what makes his camera worth anything."""
    if OLLAMA_MODEL:
        return OLLAMA_MODEL
    installed = ollama_models()
    for name in installed:
        if any(v in name.lower() for v in VISION_MODELS):
            return name
    return installed[0] if installed else ""


def model_can_see(name):
    return any(v in (name or "").lower() for v in VISION_MODELS)


def ask_ollama(history, user_text, jpeg, system, model):
    """One exchange with a local model. Returns (say, mood, move)."""
    messages = [{"role": "system", "content": system + JSON_RULES}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})

    current = {"role": "user", "content": user_text}
    if jpeg and model_can_see(model):
        current["images"] = [base64.b64encode(jpeg).decode("ascii")]
    messages.append(current)

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.8, "num_predict": 200},
    }
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode("utf-8"),
        method="POST", headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            "Can't reach Ollama on this computer. Install it from "
            "https://ollama.com, then run 'ollama pull llama3.2' once, and "
            f"leave it running. ({e.reason})") from e

    content = (body.get("message") or {}).get("content", "")
    try:
        parsed = json.loads(content)
    except ValueError:
        # Shouldn't happen with format=json, but a stray model might still
        # wrap it in prose -- take what he said and carry on unbothered.
        return content.strip()[:200] or "...", "neutral", "none"

    say = str(parsed.get("say") or "").strip() or "..."
    mood = str(parsed.get("mood") or "neutral").strip().lower()
    move = str(parsed.get("move") or "none").strip().lower()
    return say, (mood if mood in FACE_MOODS else "neutral"), (move if move in MOVES else "none")


def apply_move(link, move):
    """Carry out one of the MOVES. Returns a description, or None."""
    pair = MOVES.get(move)
    if not pair:
        return None
    action, argument = pair
    if action == "drive":
        link.drive(argument)
        return f"Driving {argument}."
    if action == "turn":
        link.turn(argument)
        return f"Turning {argument}."
    if action == "head":
        link.head(argument)
        return f"Looking {argument}."
    if action == "lift":
        link.lift(argument)
        return f"Lift {argument}."
    if action == "lights":
        link.lights(argument)
        return f"Lights -> {argument}."
    return None


def brain_name():
    """Which brain will be used, as something printable."""
    if API_KEY and API_KEY != "PASTE_YOUR_KEY_HERE":
        return "claude"
    model = pick_ollama_model()
    return f"ollama:{model}" if model else ""


def brain_think(history, user_text, jpeg, system):
    """Ask whichever brain is available. Returns (say, mood, move_desc)."""
    if API_KEY and API_KEY != "PASTE_YOUR_KEY_HERE":
        return _think_with_claude(history, user_text, jpeg, system)

    model = pick_ollama_model()
    if not model:
        raise RuntimeError(
            "No brain available. Install Ollama from https://ollama.com, "
            "then run 'ollama pull llama3.2' once in Command Prompt. "
            "(It's free and needs no account -- unlike an API key.)")

    say, mood, move = ask_ollama(history, user_text, jpeg, system, model)
    set_mood(mood)
    return say, mood, apply_move(link, move)


def _think_with_claude(history, user_text, jpeg, system):
    turn = [{"type": "text", "text": user_text}]
    if jpeg:
        turn.insert(0, {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.b64encode(jpeg).decode("ascii")},
        })
    messages = [{"role": t["role"], "content": t["content"]} for t in history]
    messages.append({"role": "user", "content": turn})

    response = call_claude(messages, system=system, max_tokens=300)
    say = ""
    move_desc = None
    for block in response.get("content", []):
        if block.get("type") == "text" and block["text"].strip():
            say = block["text"].strip()
        elif block.get("type") == "tool_use":
            move_desc = run_tool(link, block["name"], block.get("input", {}))
    return (say or "..."), current_mood(), move_desc


def run_tool(link, name, tool_input):
    if name == "drive":
        link.drive(tool_input["direction"])
        return f"Driving {tool_input['direction']}."
    if name == "turn":
        link.turn(tool_input["direction"])
        return f"Turning {tool_input['direction']}."
    if name == "look":
        link.head(tool_input["direction"])
        return f"Looking {tool_input['direction']}."
    if name == "lights":
        link.lights(tool_input["color"])
        return f"Lights -> {tool_input['color']}."
    if name == "face":
        set_mood(tool_input["mood"])
        return f"Face -> {tool_input['mood']}."
    if name == "wait":
        return "Just watching."
    return f"Unknown tool: {name}"


HOST = "0.0.0.0"
PORT = 8080

link = None
_camera_stop = False
_latest_jpeg = None
_latest_jpeg_lock = threading.Lock()

# ---- Autonomous AI mode -- Claude looks through Cozmo's camera and picks
# his next move, started and stopped from a button on the web page.
_ai_thread = None
_ai_stop_event = threading.Event()
_ai_running = False
_ai_log = []
_ai_log_lock = threading.Lock()


def _ai_log_line(text):
    with _ai_log_lock:
        _ai_log.append(text)
        del _ai_log[:-40]


# ---- His face. A mood is just a shape for his eyes; the loop below keeps
# them on screen, blinks them, and lets them wander a little so he looks
# alive even when nothing is happening.
_mood = "neutral"
_mood_lock = threading.Lock()
_face_stop = False


def set_mood(mood):
    global _mood
    with _mood_lock:
        _mood = mood if mood in FACE_MOODS else "neutral"


def current_mood():
    with _mood_lock:
        return _mood


def _face_loop():
    next_blink = time.time() + random.uniform(2.5, 6.0)
    next_glance = time.time() + random.uniform(4.0, 9.0)
    look_x = 0
    drawn = None
    last_draw = 0.0

    while not _face_stop:
        now = time.time()
        mood = current_mood()
        try:
            if now >= next_blink and mood != "sleepy":
                for shut in (0.55, 0.95, 0.55):
                    link.show_face(mood, blink=shut, look_x=look_x)
                    time.sleep(0.045)
                next_blink = now + random.uniform(2.5, 6.0)
                drawn = None

            if now >= next_glance:
                look_x = random.choice([-10, -6, 0, 0, 0, 6, 10])
                next_glance = now + random.uniform(4.0, 9.0)

            # Redraw on any change, and regularly regardless -- he wipes
            # his own screen if 30 seconds pass without a new picture.
            if (mood, look_x) != drawn or now - last_draw > 4.0:
                link.show_face(mood, look_x=look_x)
                drawn = (mood, look_x)
                last_draw = now
        except OSError:
            return  # socket closed on the way out

        time.sleep(0.1)


# ---- Voice companion mode -- you talk to him out loud, he talks back.
# The listening and the speaking both happen in the browser (it has speech
# recognition and a speech synthesizer built in), so there's nothing to
# install and no extra service to pay for. This side just remembers the
# conversation and asks Claude what to say.
_conversation = []
_conversation_lock = threading.Lock()

# How many past messages to carry. Each turn re-sends all of them, so this
# trades how much he remembers against what each reply costs.
MEMORY_TURNS = 16


def talk_to_cozmo(text):
    """One spoken exchange: what the person said, plus what he can see
    right now, goes to his brain; back comes something to say out loud, an
    expression, and maybe a move. Returns (spoken_reply, action)."""
    # The camera frame rides along with the newest message only. Attaching
    # it to every remembered turn would grow each request without telling
    # him anything -- he only ever needs to see *now*.
    with _latest_jpeg_lock:
        jpeg = _latest_jpeg

    with _conversation_lock:
        history = list(_conversation)

    spoken, _mood_used, action = brain_think(history, text, jpeg, COMPANION_PROMPT)

    # Remember the exchange as plain text -- dropping the image keeps the
    # stored history small, and he's already said whatever he saw in it.
    with _conversation_lock:
        _conversation.append({"role": "user", "content": text})
        _conversation.append({"role": "assistant", "content": spoken})
        del _conversation[:-MEMORY_TURNS]

    return spoken, action


def _local_ip():
    """This computer's own IP on Cozmo's Wi-Fi, so the printed URL is one you
    can actually open -- found by asking the OS which local address it'd
    use to reach Cozmo (no packets sent, just a routing-table lookup, so
    this works with no internet access)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(ROBOT_ADDR)
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def _camera_loop():
    global _latest_jpeg
    while not _camera_stop:
        jpeg = link.capture_image(timeout=2.0)
        if jpeg:
            with _latest_jpeg_lock:
                _latest_jpeg = jpeg


def _ai_loop():
    global _ai_running
    _ai_running = True
    _ai_log_line("Autonomous AI mode started -- Cozmo is now deciding for himself.")
    while not _ai_stop_event.is_set():
        try:
            # Read the frame _camera_loop() is already continuously
            # capturing for the page's live preview, instead of calling
            # link.capture_image() again here -- that method isn't safe to
            # call from two threads at once (both would fight over the
            # same "wait for the next frame" event), which was starving
            # this loop of frames even while the page's own preview kept
            # updating fine.
            with _latest_jpeg_lock:
                jpeg = _latest_jpeg

            if jpeg:
                nudge = "This is what you see right now. What do you do?"
            else:
                nudge = ("You can't see anything this turn. What do you do?")

            thought, _mood_used, action_desc = brain_think([], nudge, jpeg, SYSTEM_PROMPT)
            _ai_log_line(" -- ".join(x for x in (action_desc, thought) if x) or "(no action)")
        except RuntimeError as e:
            _ai_log_line(str(e))
        _ai_stop_event.wait(TICK_SECONDS)
    _ai_running = False
    _ai_log_line("Autonomous AI mode stopped.")


def _ai_start():
    global _ai_thread
    if _ai_running:
        return "Autonomous AI mode is already running."
    if not brain_name():
        raise ValueError(
            "No brain available. Install Ollama from https://ollama.com, then "
            "run 'ollama pull llama3.2' once in Command Prompt, and leave "
            "Ollama running. It's free and needs no account.")
    _ai_stop_event.clear()
    _ai_thread = threading.Thread(target=_ai_loop, daemon=True)
    _ai_thread.start()
    return "Starting autonomous AI mode..."


def _ai_stop():
    if not _ai_running:
        return "Autonomous AI mode isn't running."
    _ai_stop_event.set()
    return "Stopping autonomous AI mode..."


def _dispatch(path, data):
    """Runs one API action against the connected Cozmo and returns a reply
    string. Raises KeyError/ValueError on bad input -- the handler below
    turns that into a 400 response."""
    if path == "/api/ai/start":
        return _ai_start()
    if path == "/api/ai/stop":
        return _ai_stop()
    if path == "/api/forget":
        with _conversation_lock:
            _conversation.clear()
        return "Starting fresh -- I've forgotten what we were talking about."
    if path == "/api/drive":
        link.drive(data["direction"])
        return f"Driving {data['direction']}."
    if path == "/api/turn":
        link.turn(data["direction"])
        return f"Turning {data['direction']}."
    if path == "/api/stop":
        link.stop()
        return "Stopped."
    if path == "/api/head":
        link.head(data["direction"])
        return f"Looking {data['direction']}."
    if path == "/api/lift":
        link.lift(data["direction"])
        return f"Lift {data['direction']}."
    if path == "/api/lights":
        link.lights(data["color"])
        return f"Lights -> {data['color']}."
    if path == "/api/chat":
        return think(link, data.get("text", "")) or "..."
    if path == "/api/talk":
        spoken_text = (data.get("text") or "").strip()
        if not spoken_text:
            raise ValueError("Didn't catch any words.")
        spoken, action = talk_to_cozmo(spoken_text)
        return {"say": spoken, "action": action}
    raise ValueError("Unknown endpoint: " + path)


class Handler(BaseHTTPRequestHandler):
    def _send_bytes(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status=200):
        self._send_bytes(json.dumps(obj).encode("utf-8"), "application/json", status)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/mood":
            self._send_json({"ok": True, "mood": current_mood()})
        elif path == "/api/ai/log":
            with _ai_log_lock:
                lines = list(_ai_log)
            self._send_json({"ok": True, "running": _ai_running, "lines": lines})
        elif path == "/api/camera":
            with _latest_jpeg_lock:
                jpeg = _latest_jpeg
            if jpeg:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
            else:
                self._send_json({"ok": False, "error": "no frame yet"}, status=503)
        else:
            self._send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/"):
            self._send_json({"ok": False, "error": "not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "bad JSON"}, status=400)
            return
        try:
            reply = _dispatch(path, data)
        except (KeyError, ValueError) as e:
            self._send_json({"ok": False, "error": str(e)}, status=400)
            return
        except RuntimeError as e:
            # Claude was unreachable or refused the request -- that's a
            # failure of the moment, not bad input, so say so plainly
            # instead of dressing it up as a broken request.
            self._send_json({"ok": False, "error": str(e)}, status=503)
            return
        if isinstance(reply, dict):
            self._send_json({"ok": True, **reply})
        else:
            self._send_json({"ok": True, "reply": reply})

    def log_message(self, fmt, *args):
        pass  # keep the on-device console readable -- comment out to debug


class _Server(socketserver.ThreadingTCPServer):
    # Must be a class attribute, not set on the instance after construction
    # -- ThreadingTCPServer.__init__ binds the socket immediately, so
    # setting this afterward is too late to have any effect. Without it, a
    # restart right after stopping the script fails with "Address already
    # in use" until the OS lets go of the port on its own (can take a
    # minute or two).
    allow_reuse_address = True


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cozmo</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 16px; padding-bottom: 40px;
    background: #14161a; color: #e8e8ea;
    font: 16px -apple-system, system-ui, sans-serif;
  }
  h1 { font-size: 20px; margin: 0 0 12px; text-align: center; }
  #cam {
    display: block; width: 100%; max-width: 480px; aspect-ratio: 4/3;
    margin: 0 auto 14px; border-radius: 12px; background: #000;
    object-fit: contain; border: 1px solid #333;
  }
  #status {
    text-align: center; min-height: 20px; margin-bottom: 16px;
    color: #9fd6a0; font-size: 14px;
  }
  .panel {
    max-width: 480px; margin: 0 auto 18px;
    display: grid; gap: 8px;
  }
  .row { display: grid; gap: 8px; grid-auto-flow: column; grid-auto-columns: 1fr; }
  button {
    padding: 14px 8px; font-size: 15px; font-weight: 600;
    border: none; border-radius: 10px; background: #2a2d34; color: #e8e8ea;
    -webkit-tap-highlight-color: transparent;
  }
  button:active { background: #3a3f48; }
  #stopBtn { background: #7a2020; }
  #stopBtn:active { background: #9a2828; }
  .swatch { color: #14161a; }
  .swatch[data-color="green"] { background: #3ecf5e; }
  .swatch[data-color="red"] { background: #e8574a; }
  .swatch[data-color="blue"] { background: #4a90e8; }
  .swatch[data-color="white"] { background: #e8e8ea; }
  .swatch[data-color="off"] { background: #555; color: #e8e8ea; }
  .chat { display: flex; gap: 8px; }
  .chat input {
    flex: 1; padding: 12px; border-radius: 10px; border: 1px solid #444;
    background: #1c1f24; color: #e8e8ea; font-size: 15px;
  }
  .chat button { flex: 0 0 auto; padding: 12px 18px; background: #2a5a8a; }
  .label { font-size: 12px; color: #999; text-align: center; margin: -4px 0 2px; }
  /* His face, mirrored from what's actually on his screen. */
  #faceBox {
    max-width: 480px; margin: 0 auto 4px; height: 92px; border-radius: 12px;
    background: #05070a; border: 1px solid #333;
    display: flex; align-items: center; justify-content: center; gap: 18px;
  }
  .eye {
    background: #46e0ff; border-radius: 14px;
    width: 52px; height: 56px;
    transition: width .18s, height .18s, border-radius .18s, transform .18s;
  }
  #moodLabel {
    text-align: center; font-size: 12px; color: #777;
    margin-bottom: 14px; letter-spacing: .08em; text-transform: uppercase;
  }
  #aiBtn { background: #2a5a2a; }
  #aiBtn.running { background: #7a2020; }
  #micBtn { background: #2a4a7a; font-size: 17px; padding: 18px 8px; }
  #micBtn.listening { background: #7a2020; }
  #micBtn.thinking { background: #6a5a20; }
  .minor { font-size: 13px; padding: 9px 8px; background: #23262c; color: #999; }
  .convo { height: 150px; }
  .convo .me { color: #7fb3e8; }
  .convo .him { color: #9fd6a0; }
  .convo p { margin: 0 0 6px; }
  .log {
    height: 90px; overflow-y: auto; padding: 8px 10px; border-radius: 10px;
    background: #1c1f24; border: 1px solid #333; color: #aab; font-size: 12px;
    font-family: ui-monospace, monospace; white-space: pre-wrap;
  }
</style>
</head>
<body>
<h1>Cozmo Control</h1>
<img id="cam" src="/api/camera" alt="Cozmo's camera feed">
<div id="status">Connecting...</div>

<div id="faceBox">
  <div class="eye" id="eyeL"></div>
  <div class="eye" id="eyeR"></div>
</div>
<div id="moodLabel">neutral</div>

<div class="panel">
  <div class="label">Talk to Cozmo out loud -- he listens, sees you, and answers back</div>
  <div class="row"><button id="micBtn" onclick="toggleMic()">Start Talking</button></div>
  <div id="convo" class="log convo"></div>
  <div class="row"><button class="minor" onclick="send('/api/forget')">Forget our conversation</button></div>
</div>

<div class="panel">
  <div class="label">Autonomous AI -- Cozmo decides for himself, using his camera and Claude</div>
  <div class="row"><button id="aiBtn" onclick="toggleAi()">Start AI Mode</button></div>
  <div id="aiLog" class="log"></div>
</div>

<div class="panel">
  <div class="label">Drive</div>
  <div class="row"><button onclick="send('/api/drive',{direction:'forward'})">Forward</button></div>
  <div class="row">
    <button onclick="send('/api/turn',{direction:'left'})">Left</button>
    <button id="stopBtn" onclick="send('/api/stop')">STOP</button>
    <button onclick="send('/api/turn',{direction:'right'})">Right</button>
  </div>
  <div class="row"><button onclick="send('/api/drive',{direction:'backward'})">Backward</button></div>
</div>

<div class="panel">
  <div class="label">Head / Lift</div>
  <div class="row">
    <button onclick="send('/api/head',{direction:'up'})">Head Up</button>
    <button onclick="send('/api/head',{direction:'center'})">Head Center</button>
    <button onclick="send('/api/head',{direction:'down'})">Head Down</button>
  </div>
  <div class="row">
    <button onclick="send('/api/lift',{direction:'up'})">Lift Up</button>
    <button onclick="send('/api/lift',{direction:'down'})">Lift Down</button>
  </div>
</div>

<div class="panel">
  <div class="label">Lights</div>
  <div class="row">
    <button class="swatch" data-color="green" onclick="send('/api/lights',{color:'green'})">Green</button>
    <button class="swatch" data-color="red" onclick="send('/api/lights',{color:'red'})">Red</button>
    <button class="swatch" data-color="blue" onclick="send('/api/lights',{color:'blue'})">Blue</button>
    <button class="swatch" data-color="white" onclick="send('/api/lights',{color:'white'})">White</button>
    <button class="swatch" data-color="off" onclick="send('/api/lights',{color:'off'})">Off</button>
  </div>
</div>

<div class="panel">
  <div class="label">Talk to Cozmo (offline chat + free-form move commands)</div>
  <div class="chat">
    <input id="chatInput" type="text" placeholder="e.g. spin, tell me a joke..."
           onkeydown="if(event.key==='Enter')sendChat()">
    <button onclick="sendChat()">Send</button>
  </div>
</div>

<script>
function setStatus(text) { document.getElementById('status').textContent = text; }

async function send(path, body) {
  setStatus('...');
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})
    });
    const data = await res.json();
    setStatus(data.ok ? data.reply : ('Error: ' + data.error));
  } catch (e) {
    setStatus('Connection error -- is the server still running?');
  }
}

function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  send('/api/chat', {text: text});
}

// Poll the camera feed -- simpler and more compatible than an MJPEG stream,
// plenty smooth enough for "see what he sees" at a robot's speed.
setInterval(() => {
  document.getElementById('cam').src = '/api/camera?t=' + Date.now();
}, 1200);

let aiRunning = false;

async function toggleAi() {
  const path = aiRunning ? '/api/ai/stop' : '/api/ai/start';
  try {
    const res = await fetch(path, {method: 'POST'});
    const data = await res.json();
    setStatus(data.ok ? data.reply : ('Error: ' + data.error));
  } catch (e) {
    setStatus('Connection error -- is the server still running?');
  }
  pollAiLog();
}

async function pollAiLog() {
  try {
    const res = await fetch('/api/ai/log');
    const data = await res.json();
    aiRunning = data.running;
    const btn = document.getElementById('aiBtn');
    btn.textContent = aiRunning ? 'Stop AI Mode' : 'Start AI Mode';
    btn.classList.toggle('running', aiRunning);
    const box = document.getElementById('aiLog');
    box.textContent = data.lines.join('\\n');
    box.scrollTop = box.scrollHeight;
  } catch (e) {
    // server not reachable this tick -- next poll will retry
  }
}

setInterval(pollAiLog, 3000);
pollAiLog();

// ---------- Mirror of the face that's actually on his screen, so you can
// see his expression without leaning over to look at the robot.
const EYE_SHAPES = {
  neutral:   {w: 52, h: 56, r: 15, y: 0},
  happy:     {w: 52, h: 46, r: 20, y: 3},
  excited:   {w: 58, h: 66, r: 18, y: 0},
  curious:   {w: 52, h: 56, r: 15, y: 0, uneven: 14},
  sleepy:    {w: 52, h: 16, r: 8,  y: 14},
  sad:       {w: 48, h: 40, r: 14, y: 8, tilt: -12},
  annoyed:   {w: 52, h: 38, r: 10, y: 2, tilt: 12},
  surprised: {w: 46, h: 66, r: 23, y: 0}
};

let shownMood = null;

function paintFace(mood) {
  if (mood === shownMood) return;
  shownMood = mood;
  const s = EYE_SHAPES[mood] || EYE_SHAPES.neutral;
  const eyes = [document.getElementById('eyeL'), document.getElementById('eyeR')];
  eyes.forEach((eye, i) => {
    const h = (s.uneven && i === 0) ? s.h - s.uneven : s.h;
    eye.style.width = s.w + 'px';
    eye.style.height = h + 'px';
    eye.style.borderRadius = s.r + 'px';
    const tilt = s.tilt ? (i === 0 ? s.tilt : -s.tilt) : 0;
    eye.style.transform = 'translateY(' + s.y + 'px) rotate(' + tilt + 'deg)';
  });
  document.getElementById('moodLabel').textContent = mood;
}

async function pollMood() {
  try {
    const res = await fetch('/api/mood');
    const data = await res.json();
    paintFace(data.mood);
  } catch (e) { /* next poll will retry */ }
}

setInterval(pollMood, 1000);
pollMood();

// ---------- Voice: he listens through your microphone and answers out
// loud. Both halves are built into the browser, so there's nothing extra
// to install. Speech recognition is Chrome/Edge only, which is why the
// button explains itself rather than silently doing nothing elsewhere.
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let micOn = false;
let speaking = false;

function addLine(who, text) {
  const box = document.getElementById('convo');
  const p = document.createElement('p');
  p.className = who === 'me' ? 'me' : 'him';
  p.textContent = (who === 'me' ? 'You: ' : 'Cozmo: ') + text;
  box.appendChild(p);
  box.scrollTop = box.scrollHeight;
}

function setMicButton(state) {
  const btn = document.getElementById('micBtn');
  btn.classList.remove('listening', 'thinking');
  if (state === 'listening') {
    btn.classList.add('listening');
    btn.textContent = 'Listening... (tap to stop)';
  } else if (state === 'thinking') {
    btn.classList.add('thinking');
    btn.textContent = 'Thinking...';
  } else {
    btn.textContent = 'Start Talking';
  }
}

function speak(text) {
  // Stop listening while he talks, otherwise the microphone picks up his
  // own voice and he ends up answering himself.
  speaking = true;
  if (recognition) { try { recognition.stop(); } catch (e) {} }

  const utter = new SpeechSynthesisUtterance(text);
  utter.pitch = 1.4;   // higher than default -- small robot, small voice
  utter.rate = 1.05;
  utter.onend = () => {
    speaking = false;
    if (micOn) { startRecognition(); }
  };
  utter.onerror = () => {
    speaking = false;
    if (micOn) { startRecognition(); }
  };
  window.speechSynthesis.speak(utter);
}

async function heard(text) {
  addLine('me', text);
  setMicButton('thinking');
  try {
    const res = await fetch('/api/talk', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: text})
    });
    const data = await res.json();
    if (data.ok) {
      addLine('him', data.say);
      if (data.action) { setStatus(data.action); }
      speak(data.say);
    } else {
      addLine('him', '(' + data.error + ')');
      setStatus('Error: ' + data.error);
      speaking = false;
      if (micOn) { startRecognition(); }
    }
  } catch (e) {
    setStatus('Connection error -- is the script still running?');
    speaking = false;
    if (micOn) { startRecognition(); }
  }
  if (micOn) { setMicButton('listening'); }
}

function startRecognition() {
  if (!recognition || speaking) return;
  try { recognition.start(); } catch (e) { /* already started -- fine */ }
}

function toggleMic() {
  if (!SpeechRec) {
    setStatus('This browser can\\'t listen. Use Chrome or Edge for voice.');
    return;
  }
  micOn = !micOn;
  if (!micOn) {
    setMicButton('off');
    if (recognition) { try { recognition.stop(); } catch (e) {} }
    setStatus('Stopped listening.');
    return;
  }

  if (!recognition) {
    recognition = new SpeechRec();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      const text = event.results[event.results.length - 1][0].transcript.trim();
      if (text) { heard(text); }
    };
    // Chrome ends recognition on its own after a pause, so to stay
    // always-on it has to be restarted each time it stops.
    recognition.onend = () => { if (micOn && !speaking) { startRecognition(); } };
    recognition.onerror = (event) => {
      if (event.error === 'not-allowed') {
        micOn = false;
        setMicButton('off');
        setStatus('Microphone permission denied -- allow it and try again.');
      }
    };
  }

  setMicButton('listening');
  setStatus('Listening -- just talk to him.');
  startRecognition();
}

setStatus('Ready.');
</script>
</body>
</html>
"""


def _count_camera_packets(link):
    """Wraps the image-chunk handler so startup can report whether camera
    data is actually arriving -- the difference between 'a firewall is
    eating the packets' and 'they arrive but don't assemble' is invisible
    otherwise, and a silently black camera is the single most confusing
    way this can fail."""
    counter = {"chunks": 0}
    original = link._handle_image_chunk

    def counting_handler(payload):
        counter["chunks"] += 1
        original(payload)

    link._handle_image_chunk = counting_handler
    return counter


def _report_camera_status(counter, seconds=8.0):
    print()
    print(f"Checking Cozmo's camera (up to {int(seconds)} seconds)...")
    deadline = time.time() + seconds
    while time.time() < deadline:
        with _latest_jpeg_lock:
            got_frame = _latest_jpeg is not None
        if got_frame:
            print("  Camera is working -- you'll see what he sees on the page.")
            return
        time.sleep(0.25)

    if counter["chunks"] == 0:
        print("  No camera data is reaching this computer at all.")
        print("  Everything else (driving, lights, chat) still works -- but the")
        print("  camera view will stay black, and AI Mode will be blind.")
        print("  This is almost always a firewall. On Windows: open Windows")
        print("  Defender Firewall > Allow an app through firewall, and make")
        print("  sure Python is allowed on Private networks.")
    else:
        print(f"  Camera data IS arriving ({counter['chunks']} packets), but it")
        print("  isn't assembling into complete pictures. Some packets are")
        print("  probably getting dropped -- try moving closer to Cozmo.")


def main():
    global link, _camera_stop

    print("Connecting to Cozmo...")
    link = CozmoLink()
    if not link.connect(timeout=8.0):
        print("Couldn't connect within 8 seconds.")
        print("Check: is this computer's Wi-Fi joined to Cozmo's own network "
              "(not your home Wi-Fi)? Is Cozmo awake (on his charger, lift "
              "raised and lowered once)?")
        return

    camera_counter = _count_camera_packets(link)
    threading.Thread(target=_camera_loop, daemon=True).start()

    # Wake his face up before anything else -- eyes on the screen are the
    # clearest sign that the connection is actually live.
    set_mood("happy")
    threading.Thread(target=_face_loop, daemon=True).start()
    link.lights("green")

    # A port left over from a previous run that didn't fully release
    # would otherwise crash this with "Address already in use" -- try
    # nearby ports instead of giving up on the first one.
    server = None
    port = PORT
    for port in range(PORT, PORT + 10):
        try:
            server = _Server((HOST, port), Handler)
            break
        except OSError:
            continue
    if server is None:
        print(f"Couldn't bind to any port in {PORT}-{PORT + 9} -- they all seem "
              f"to be in use. Close any other copy of this script that's still "
              f"running and try again.")
        link.disconnect()
        return

    _report_camera_status(camera_counter)

    print()
    brain = brain_name()
    if not brain:
        print("His brain isn't set up yet, so talking and AI Mode won't work.")
        print("  Install Ollama from https://ollama.com, then run this once:")
        print("      ollama pull llama3.2")
        print("  (free, no account, no API key -- and it needs no internet")
        print("   once installed). Everything else works without it.")
    elif brain.startswith("ollama:"):
        model = brain.split(":", 1)[1]
        print(f"Brain: Ollama, using {model} -- running on this computer, no internet needed.")
        if not model_can_see(model):
            print(f"  ({model} is text-only, so he can talk but not see. For eyes,")
            print("   run 'ollama pull llava' and restart this.)")
    else:
        print("Brain: Claude (using your API key).")

    print()
    print("=" * 60)
    print("Cozmo is ready! Open this link in your browser:")
    print(f"    http://{_local_ip()}:{port}/")
    print("=" * 60)
    print("(Any device on Cozmo's Wi-Fi can open it, not just this computer.)")
    print("Leave this running. Press the stop button to end it.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        global _face_stop
        _camera_stop = True
        _face_stop = True
        _ai_stop_event.set()
        time.sleep(0.2)  # let the face loop finish its current draw
        server.shutdown()
        server.server_close()
        link.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    # Double-clicking this file opens a console window that closes the
    # instant the program ends -- including when it ends because of a
    # crash, which would otherwise make the error impossible to read.
    # Holding the window open here is what lets this file be run by
    # double-clicking it, with no .bat launcher needed.
    try:
        main()
    except Exception:
        traceback.print_exc()
        print()
        print("Cozmo stopped because of the error above.")
    finally:
        if os.name == "nt":
            try:
                input("\nPress Enter to close this window...")
            except EOFError:
                pass
