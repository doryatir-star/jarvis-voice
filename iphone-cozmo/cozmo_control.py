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
                data, _ = self.sock.recvfrom(2048)
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
            self.ready = True
            self.on_log("Cozmo ready!")

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


# ---------- Tiny command language, so this doubles as a text "AI" you talk to ----------

def handle_command(link, text):
    t = text.strip().lower()
    if not t:
        return
    if t in ("forward", "fwd", "move forward", "go forward"):
        link.drive("forward"); print("Moving forward.")
    elif t in ("backward", "back", "move backward", "go backward"):
        link.drive("backward"); print("Moving backward.")
    elif t in ("left", "turn left"):
        link.turn("left"); print("Turning left.")
    elif t in ("right", "turn right"):
        link.turn("right"); print("Turning right.")
    elif t in ("stop", "halt"):
        link.stop(); print("Stopping.")
    elif t in ("head up", "look up"):
        link.head("up"); print("Looking up.")
    elif t in ("head down", "look down"):
        link.head("down"); print("Looking down.")
    elif t in ("head center", "look straight", "look forward"):
        link.head("center"); print("Centering head.")
    elif t in ("lift up",):
        link.lift("up"); print("Lift up.")
    elif t in ("lift down",):
        link.lift("down"); print("Lift down.")
    elif t.startswith("lights "):
        color = t.split(" ", 1)[1].strip()
        link.lights(color); print(f"Lights -> {color}.")
    else:
        print("Didn't understand. Try: forward, backward, left, right, stop, "
              "head up/down/center, lift up/down, lights <green/red/blue/white/off>, quit")


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
    print("Cozmo is ready! Type a command and press return.")
    print("Commands: forward, backward, left, right, stop, head up/down/center, "
          "lift up/down, lights green/red/blue/white/off, quit")
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
            handle_command(link, cmd)
    finally:
        link.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
