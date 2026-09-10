"""Control a real Cozmo robot directly from your iPhone — no computer,
no Mac, no Xcode. Just paste this whole file into an on-device Python app
(Pythonista 3, Pyto, or a-Shell all work) and run it.

Why this works with no app-store app of its own: this file uses ONLY the
Python standard library (socket, struct, threading, time, math) — nothing
to `pip install`, nothing to compile. Any of those Python apps can run it
as-is.

How it works: Cozmo doesn't use Bluetooth — he creates his own Wi-Fi
hotspot and speaks a custom (undocumented, reverse-engineered) protocol
over plain UDP. This file reimplements that protocol directly. It is NOT
guesswork: every byte this file puts on the wire was checked, one packet
type at a time, against the real `pycozmo` reference library
(https://github.com/zayfod/pycozmo) — the same one the Windows desktop
version of this project (cozmo_hub.py) uses — and confirmed byte-for-byte
identical before this file was written. See ios-cozmo-app/ in this repo
for a from-scratch Swift reimplementation of the same protocol that did
NOT have that kind of verification available (no Cozmo/Mac to test
against) — this file is the more trustworthy of the two.

=====================================================================
SETUP — do this before running the script
=====================================================================
1. Install a Python app from the App Store: Pythonista 3 (paid, most
   mature, recommended) or Pyto or a-Shell (both free) all support raw
   UDP sockets, which is all this needs.
2. Put Cozmo on his charger to wake him up.
3. Raise and lower his lift with your hand — his screen shows a Wi-Fi
   network name and password.
4. In iOS Settings > Wi-Fi, join THAT network with your iPhone (not your
   home Wi-Fi — Cozmo's hotspot usually has no internet, which is fine,
   you don't need internet for this).
5. Open your Python app, create a new script, paste in this whole file,
   and run it.

IMPORTANT — iOS suspends apps that aren't on screen. If you lock your
phone, switch apps, or let the screen turn off, Cozmo will disconnect
(the required keep-alive ping stops firing). Keep this app open and your
screen on while you're driving him.
=====================================================================
"""
import math
import random
import re
import socket
import struct
import threading
import time

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


def main():
    print("Connecting to Cozmo...")
    link = CozmoLink()
    if not link.connect(timeout=8.0):
        print("Couldn't connect within 8 seconds.")
        print("Check: is your iPhone's Wi-Fi joined to Cozmo's own network "
              "(not your home Wi-Fi)? Is Cozmo awake (on his charger, lift "
              "raised and lowered once)?")
        return
    print()
    print("Cozmo is ready! Type naturally -- \"go forward\", \"can you turn left\", "
          "\"look up\", \"tell me a joke\" -- or 'quit' to disconnect.")
    print("Movement: forward/backward, left/right, spin, stop, look up/down/straight, "
          "lift up/down, lights green/red/blue/white/off.")
    print("Chat: jokes, time, date, coin flip, dice, basic math, small talk "
          "(all offline -- no internet out here on Cozmo's own Wi-Fi).")
    print("(Keep this app open and your screen on -- iOS disconnects Cozmo "
          "if this app gets backgrounded.)")
    try:
        while True:
            try:
                cmd = input("> ")
            except EOFError:
                break
            if cmd.strip().lower() in ("quit", "exit"):
                break
            think(link, cmd)
    finally:
        link.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
