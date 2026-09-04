"""Anki/Digital Dream Labs Cozmo control over Wi-Fi — uses pycozmo, a pure
Python reimplementation of Cozmo's UDP protocol. No phone, no official app,
no SDK tether required: once your PC is joined to Cozmo's own Wi-Fi access
point, this module talks to the robot directly.

Mirrors lego_hub.py's idioms: a background daemon thread, callback-based
status reporting, and functions that never raise out to the caller (any
failure becomes a spoken string instead of a crash).
"""
import math
import os
import tempfile
import threading
import time
import traceback

try:
    import pycozmo
    _PYCOZMO_OK = True
except Exception:
    _PYCOZMO_OK = False


LOG_PATH = os.path.join(tempfile.gettempdir(), "jarvis_cozmo.log")

# Cozmo's own hardware limits (see pycozmo.robot).
MAX_WHEEL_SPEED_MMPS = 200.0
MIN_HEAD_ANGLE_DEG = -25.0
MAX_HEAD_ANGLE_DEG = 44.5
MIN_LIFT_HEIGHT_MM = 32.0
MAX_LIFT_HEIGHT_MM = 92.0

HEAD_DOWN_DEG = MIN_HEAD_ANGLE_DEG + 5.0
HEAD_UP_DEG = MAX_HEAD_ANGLE_DEG - 5.0

_LIGHT_NAMES = ("green", "red", "blue", "white", "off")


def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass


class CozmoHub:
    def __init__(self, drive_speed=100.0, drive_seconds=1.5,
                 turn_speed=80.0, turn_seconds=0.8,
                 on_status=None, on_error=None):
        self.drive_speed = min(max(drive_speed, 0.0), MAX_WHEEL_SPEED_MMPS)
        self.drive_seconds = drive_seconds
        self.turn_speed = min(max(turn_speed, 0.0), MAX_WHEEL_SPEED_MMPS)
        self.turn_seconds = turn_seconds
        self.on_status = on_status or (lambda s: None)
        self.on_error = on_error or (lambda m: None)

        self._client = None
        self._connected = threading.Event()
        self._retry_backoff = 5.0
        self._warned = False
        self._anims_loaded = False

    def start(self):
        """Kick off connection in the background. Never blocks the caller."""
        if not _PYCOZMO_OK:
            _log("pycozmo not installed/importable")
            self.on_error("Cozmo support isn't installed.")
            return
        threading.Thread(target=self._connect_loop, daemon=True).start()

    def _connect_loop(self):
        while True:
            cli = None
            try:
                self.on_status("connecting")
                cli = pycozmo.Client()
                cli.start()
                cli.connect()
                cli.wait_for_robot(timeout=8.0)
                self._client = cli
                self._connected.set()
                self._warned = False
                self.on_status("connected")
                _log("connected")
                try:
                    cli.load_anims()
                    self._anims_loaded = True
                except Exception:
                    _log("load_anims failed:\n" + traceback.format_exc())
                return
            except Exception:
                _log("connect failed:\n" + traceback.format_exc())
                try:
                    if cli is not None:
                        cli.stop()
                except Exception:
                    pass
                if not self._warned:
                    self._warned = True
                    self.on_status("offline")
                    self.on_error(
                        "I can't reach Cozmo. Make sure he's awake — raise "
                        "and lower his lift on the charger — and that this "
                        "PC's Wi-Fi is connected to Cozmo's own network."
                    )
                time.sleep(self._retry_backoff)

    def is_connected(self) -> bool:
        return self._connected.is_set() and self._client is not None

    def drive(self, direction: str) -> str:
        if not self.is_connected():
            return "Cozmo isn't connected."
        try:
            speed = self.drive_speed if direction == "forward" else -self.drive_speed
            self._client.drive_wheels(
                lwheel_speed=speed, rwheel_speed=speed, duration=self.drive_seconds)
            return f"Moving {direction}."
        except Exception as e:
            _log("drive failed:\n" + traceback.format_exc())
            return f"Couldn't move {direction}: {e}"

    def turn(self, direction: str) -> str:
        if not self.is_connected():
            return "Cozmo isn't connected."
        try:
            if direction == "left":
                left, right = -self.turn_speed, self.turn_speed
            else:
                left, right = self.turn_speed, -self.turn_speed
            self._client.drive_wheels(
                lwheel_speed=left, rwheel_speed=right, duration=self.turn_seconds)
            return f"Turning {direction}."
        except Exception as e:
            _log("turn failed:\n" + traceback.format_exc())
            return f"Couldn't turn {direction}: {e}"

    def stop_all(self) -> str:
        if not self.is_connected():
            return "Cozmo isn't connected."
        try:
            self._client.stop_all_motors()
            return "Stopping."
        except Exception as e:
            _log("stop failed:\n" + traceback.format_exc())
            return f"Couldn't stop: {e}"

    def turn_head(self, direction: str) -> str:
        if not self.is_connected():
            return "Cozmo isn't connected."
        try:
            deg = {"up": HEAD_UP_DEG, "down": HEAD_DOWN_DEG, "center": 0.0}.get(direction, 0.0)
            self._client.set_head_angle(angle=math.radians(deg))
            return "Centering my head." if direction == "center" else f"Looking {direction}."
        except Exception as e:
            _log("turn_head failed:\n" + traceback.format_exc())
            return f"Couldn't move my head: {e}"

    def lift(self, action: str) -> str:
        if not self.is_connected():
            return "Cozmo isn't connected."
        try:
            height = MAX_LIFT_HEIGHT_MM if action == "up" else MIN_LIFT_HEIGHT_MM
            self._client.set_lift_height(height=height)
            return f"Lift {action}."
        except Exception as e:
            _log("lift failed:\n" + traceback.format_exc())
            return f"Couldn't move my lift: {e}"

    def lights(self, color: str) -> str:
        if not self.is_connected():
            return "Cozmo isn't connected."
        color = (color or "").lower()
        if color not in _LIGHT_NAMES:
            return f"I don't know the light color {color!r}."
        try:
            light = getattr(pycozmo.lights, f"{color}_light")
            self._client.set_all_backpack_lights(light)
            return "Lights off." if color == "off" else f"Lights {color}."
        except Exception as e:
            _log("lights failed:\n" + traceback.format_exc())
            return f"Couldn't change my lights: {e}"

    def play_anim(self, name: str) -> str:
        if not self.is_connected():
            return "Cozmo isn't connected."
        name = (name or "").strip()
        if not name:
            return "Play which animation?"
        if not self._anims_loaded:
            return "My animation clips didn't load — run pycozmo_resources.py download."
        try:
            self._client.play_anim(name)
            return f"Playing {name}."
        except Exception as e:
            _log("play_anim failed:\n" + traceback.format_exc())
            return f"Couldn't play {name!r}: {e}"

    def disconnect(self):
        try:
            if self._client is not None:
                self._client.stop_all_motors()
                self._client.disconnect()
                self._client.stop()
        except Exception:
            pass
        self._connected.clear()
