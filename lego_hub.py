"""LEGO BOOST Move Hub control over Bluetooth LE — stock LEGO firmware, no
Pybricks/custom firmware needed. Uses pylgbst's bleak backend, which speaks
LEGO's native LWP3 protocol.

Mirrors voice.py's idioms: a background daemon thread, callback-based status
reporting, and functions that never raise out to the caller (any failure
becomes a spoken string instead of a crash).
"""
import os
import tempfile
import threading
import time
import traceback

try:
    from pylgbst import get_connection_bleak
    from pylgbst.hub import MoveHub
    _PYLGBST_OK = True
except Exception:
    _PYLGBST_OK = False


LOG_PATH = os.path.join(tempfile.gettempdir(), "jarvis_hub.log")


def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass


class LegoHub:
    def __init__(self, hub_name="LEGO Move Hub", hub_mac="",
                 claw_port="D", head_port="C",
                 drive_speed=0.6, drive_seconds=1.5, turn_seconds=0.8,
                 left_invert=False, right_invert=False,
                 on_status=None, on_error=None):
        self.hub_name = hub_name
        self.hub_mac = hub_mac
        self.claw_port = claw_port.upper()
        self.head_port = head_port.upper()
        self.drive_speed = drive_speed
        self.drive_seconds = drive_seconds
        self.turn_seconds = turn_seconds
        self.left_invert = left_invert
        self.right_invert = right_invert
        self.on_status = on_status or (lambda s: None)
        self.on_error = on_error or (lambda m: None)

        self._hub = None
        self._connected = threading.Event()
        self._stop_timer = None
        self._retry_backoff = 5.0
        self._warned = False
        # angled() moves are relative to the motor's current position, so we
        # track where we last told the head/claw to go and only move the
        # remaining delta — otherwise repeating "turn left" or "open the
        # claw" would keep rotating further each time instead of holding.
        self._head_angle = 0
        self._claw_angle = 0

    def start(self):
        """Kick off connection in the background. Never blocks the caller."""
        if not _PYLGBST_OK:
            _log("pylgbst not installed/importable")
            self.on_error("Rover support isn't installed.")
            return
        threading.Thread(target=self._connect_loop, daemon=True).start()

    def _connect_loop(self):
        while True:
            try:
                self.on_status("connecting")
                conn = get_connection_bleak(
                    hub_mac=self.hub_mac or None,
                    hub_name=self.hub_name or None,
                )
                self._hub = MoveHub(conn)
                # Give the hub a moment to report what's attached to C/D.
                time.sleep(1.5)
                self._connected.set()
                self._warned = False
                self.on_status("connected")
                _log("connected")
                return
            except Exception:
                _log("connect failed:\n" + traceback.format_exc())
                if not self._warned:
                    self._warned = True
                    self.on_status("offline")
                    self.on_error(
                        "I can't reach the rover. Make sure it's powered on "
                        "and awake — press its button — and within range."
                    )
                time.sleep(self._retry_backoff)

    def is_connected(self) -> bool:
        return self._connected.is_set() and self._hub is not None

    def _external_motor(self, name: str):
        port = self.claw_port if name == "claw" else self.head_port
        attr = f"port_{port}"
        motor = getattr(self._hub, attr, None)
        if motor is None:
            raise RuntimeError(f"Nothing detected on port {port} ({name}).")
        return motor

    def _cancel_timer(self):
        if self._stop_timer is not None:
            self._stop_timer.cancel()
            self._stop_timer = None

    def _schedule_stop(self, seconds: float):
        self._cancel_timer()
        self._stop_timer = threading.Timer(seconds, self._auto_stop_treads)
        self._stop_timer.daemon = True
        self._stop_timer.start()

    def _auto_stop_treads(self):
        try:
            if self._hub is not None:
                self._hub.motor_AB.stop()
        except Exception:
            _log("auto-stop failed:\n" + traceback.format_exc())

    def _tread_speeds(self, left: float, right: float):
        if self.left_invert:
            left = -left
        if self.right_invert:
            right = -right
        return left, right

    def drive(self, direction: str) -> str:
        if not self.is_connected():
            return "The rover isn't connected."
        try:
            sign = 1.0 if direction == "forward" else -1.0
            left, right = self._tread_speeds(self.drive_speed * sign, self.drive_speed * sign)
            self._hub.motor_AB.start_speed(left, right)
            self._schedule_stop(self.drive_seconds)
            return f"Moving {direction}."
        except Exception as e:
            _log("drive failed:\n" + traceback.format_exc())
            return f"Couldn't move {direction}: {e}"

    def turn(self, direction: str) -> str:
        if not self.is_connected():
            return "The rover isn't connected."
        try:
            if direction == "left":
                left, right = self._tread_speeds(-self.drive_speed, self.drive_speed)
            else:
                left, right = self._tread_speeds(self.drive_speed, -self.drive_speed)
            self._hub.motor_AB.start_speed(left, right)
            self._schedule_stop(self.turn_seconds)
            return f"Turning {direction}."
        except Exception as e:
            _log("turn failed:\n" + traceback.format_exc())
            return f"Couldn't turn {direction}: {e}"

    def stop_all(self) -> str:
        self._cancel_timer()
        if not self.is_connected():
            return "The rover isn't connected."
        try:
            self._hub.motor_AB.stop()
            return "Stopping."
        except Exception as e:
            _log("stop failed:\n" + traceback.format_exc())
            return f"Couldn't stop: {e}"

    def turn_head(self, direction: str) -> str:
        if not self.is_connected():
            return "The rover isn't connected."
        try:
            motor = self._external_motor("head")
            target = {"left": -90, "right": 90, "center": 0}.get(direction, 90)
            delta = target - self._head_angle
            if delta != 0:
                motor.angled(delta, speed_primary=0.4, wait_complete=False)
                self._head_angle = target
            return "Centering my head." if direction == "center" else "Turning my head."
        except Exception as e:
            _log("turn_head failed:\n" + traceback.format_exc())
            return f"Couldn't turn my head: {e}"

    def claw(self, action: str) -> str:
        if not self.is_connected():
            return "The rover isn't connected."
        try:
            motor = self._external_motor("claw")
            target = -60 if action == "open" else 60
            delta = target - self._claw_angle
            if delta != 0:
                motor.angled(delta, speed_primary=0.4, wait_complete=False)
                self._claw_angle = target
            return f"Claw {action}."
        except Exception as e:
            _log("claw failed:\n" + traceback.format_exc())
            return f"Couldn't {action} the claw: {e}"

    def disconnect(self):
        self._cancel_timer()
        try:
            if self._hub is not None:
                self._hub.motor_AB.stop()
        except Exception:
            pass
        self._connected.clear()
