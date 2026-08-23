import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def _app_dir() -> Path:
    # When bundled by PyInstaller, __file__ is inside a temp dir; config/.env
    # should live next to the .exe (or in %APPDATA%\Jarvis as a fallback).
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


APP_DIR = _app_dir()
ENV_PATH = APP_DIR / ".env"
if sys.platform.startswith("win"):
    FALLBACK_ENV = Path(os.getenv("APPDATA", str(APP_DIR))) / "Jarvis" / ".env"
else:
    FALLBACK_ENV = Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "jarvis" / ".env"

# Prefer .env next to the app; fall back to the OS's per-user config dir
# (%APPDATA%\Jarvis\.env on Windows, ~/.config/jarvis/.env on Linux).
for p in (ENV_PATH, FALLBACK_ENV):
    if p.exists():
        load_dotenv(p)
        break

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("JARVIS_MODEL", "claude-haiku-4-5-20251001")
WAKE_WORDS = ("jarvis", "hey jarvis")
ASSISTANT_NAME = "Jarvis"
USER_NAME = os.getenv("JARVIS_USER", "Sir")

# --- LEGO rover (optional) ---
ROBOT_HUB_NAME = os.getenv("ROBOT_HUB_NAME", "LEGO Move Hub")
ROBOT_HUB_MAC = os.getenv("ROBOT_HUB_MAC", "")
ROBOT_CLAW_PORT = os.getenv("ROBOT_CLAW_PORT", "D")
ROBOT_HEAD_PORT = os.getenv("ROBOT_HEAD_PORT", "C")
ROBOT_DRIVE_SPEED = float(os.getenv("ROBOT_DRIVE_SPEED", "0.6"))
ROBOT_DRIVE_SECONDS = float(os.getenv("ROBOT_DRIVE_SECONDS", "1.5"))
ROBOT_TURN_SECONDS = float(os.getenv("ROBOT_TURN_SECONDS", "0.8"))
ROBOT_LEFT_INVERT = os.getenv("ROBOT_LEFT_INVERT", "false").lower() == "true"
ROBOT_RIGHT_INVERT = os.getenv("ROBOT_RIGHT_INVERT", "false").lower() == "true"
