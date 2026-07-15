"""One-time setup script: figure out which external port (C or D) drives the
claw vs. the head, and which polarity each tread motor needs, then write the
answers into .env. Run this once after wiring the robot, with the hub
powered on and awake (press its button first).

    python calibrate_ports.py
"""
import sys
from pathlib import Path

from pylgbst import get_connection_bleak
from pylgbst.hub import MoveHub

from config import ROBOT_HUB_NAME, ROBOT_HUB_MAC, ENV_PATH


def ask(prompt: str) -> bool:
    return input(prompt + " [y/n] ").strip().lower().startswith("y")


def write_env(updates: dict):
    path = ENV_PATH
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    keys_seen = set()
    for i, line in enumerate(lines):
        for k, v in updates.items():
            if line.strip().startswith(f"{k}="):
                lines[i] = f"{k}={v}"
                keys_seen.add(k)
    for k, v in updates.items():
        if k not in keys_seen:
            lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote settings to {path}")


def main():
    print(f"Connecting to {ROBOT_HUB_NAME!r}... (press the hub's button if it's asleep)")
    conn = get_connection_bleak(hub_mac=ROBOT_HUB_MAC or None, hub_name=ROBOT_HUB_NAME or None)
    hub = MoveHub(conn)
    print("Connected. Waiting for the hub to report attached motors...")
    import time
    time.sleep(2)

    updates = {}

    for port_letter in ("C", "D"):
        motor = getattr(hub, f"port_{port_letter}", None)
        if motor is None:
            print(f"Port {port_letter}: nothing detected, skipping.")
            continue
        print(f"\nNudging port {port_letter}...")
        motor.angled(90, speed_primary=0.4, wait_complete=True)
        if ask(f"Port {port_letter}: did the CLAW move?"):
            updates["ROBOT_CLAW_PORT"] = port_letter
        elif ask(f"Port {port_letter}: did the HEAD move?"):
            updates["ROBOT_HEAD_PORT"] = port_letter
        else:
            print(f"Port {port_letter}: not recognized, leaving unset.")

    print("\nNow checking tread motor polarity...")
    hub.motor_A.start_speed(0.4)
    time.sleep(0.8)
    hub.motor_A.stop()
    updates["ROBOT_LEFT_INVERT"] = "false" if ask("Did the LEFT tread spin FORWARD?") else "true"

    hub.motor_B.start_speed(0.4)
    time.sleep(0.8)
    hub.motor_B.stop()
    updates["ROBOT_RIGHT_INVERT"] = "false" if ask("Did the RIGHT tread spin FORWARD?") else "true"

    write_env(updates)
    print("Done. Restart Jarvis to pick up the new settings.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nCalibration failed: {e}")
        sys.exit(1)
