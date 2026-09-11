"""Cozmo Control -- EVERYTHING IN ONE FILE. No other files needed.

Just open this one file in VS Code and press the Run button (the triangle
in the top-right corner). Nothing to install, nothing to `pip install` --
this uses only Python's standard library.

=====================================================================
WHAT IT DOES
=====================================================================
Starts a little website on your own computer that controls a real Cozmo:
  * Buttons to drive, turn, tilt his head, raise his lift, change lights
  * A live view from his camera
  * A text box to talk to him (works with no internet)
  * A "Start AI Mode" button -- Claude looks through Cozmo's camera and
    decides what he does next, all on his own

When you run it, it prints a link like http://172.31.1.2:8080/ --
open that link in your browser to get the control page.

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

For AI Mode you also need an Anthropic API key (from
https://console.anthropic.com -- it's pay-as-you-go, real money, usually
a fraction of a cent per decision). Paste it into the API_KEY line below.

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
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "PASTE_YOUR_KEY_HERE")

MODEL = "claude-opus-5"
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# How long to wait between autonomous decisions. Shorter feels livelier,
# but costs more (one Claude call, with an image, per tick).
TICK_SECONDS = 8

SYSTEM_PROMPT = (
    "You are Cozmo, a small, curious, playful robot with a camera for eyes. "
    "Nobody is chatting with you right now -- you decide entirely on your "
    "own what to do next, once every few seconds, based on what you "
    "actually see through your camera. Always call exactly one tool each "
    "turn. Be curious: react to what's in front of you, explore, don't "
    "repeat the same action over and over. You may add one short sentence "
    "about what you're thinking, for a log nobody reads live, so keep it "
    "brief. If the image is blank, dark, or you're facing a wall, that's a "
    "good reason to turn or move rather than staying put."
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
        "name": "wait",
        "description": "Do nothing this turn -- stay put and keep watching.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def call_claude(messages):
    payload = {
        "model": MODEL,
        "max_tokens": 512,
        "system": SYSTEM_PROMPT,
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
            content = []
            if jpeg:
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg",
                               "data": base64.b64encode(jpeg).decode("ascii")},
                })
                content.append({"type": "text", "text": "This is what you see right now. What do you do?"})
            else:
                content.append({"type": "text", "text":
                                 "Your camera frame didn't arrive in time this turn. What do you do?"})

            response = call_claude([{"role": "user", "content": content}])
            thought = None
            action_desc = None
            for block in response.get("content", []):
                if block.get("type") == "text" and block["text"].strip():
                    thought = block["text"].strip()
                elif block.get("type") == "tool_use":
                    action_desc = run_tool(link, block["name"], block.get("input", {}))
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
    if not API_KEY or API_KEY == "PASTE_YOUR_KEY_HERE":
        raise ValueError(
            "No Anthropic API key set. Open this file, find the API_KEY line near "
            "the top, and paste your key in (get one at "
            "https://console.anthropic.com).")
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
  #aiBtn { background: #2a5a2a; }
  #aiBtn.running { background: #7a2020; }
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
        _camera_stop = True
        _ai_stop_event.set()
        server.shutdown()
        server.server_close()
        link.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
