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
APPDATA_ENV = Path(os.getenv("APPDATA", str(APP_DIR))) / "Jarvis" / ".env"

# Prefer .env next to the exe; fall back to %APPDATA%\Jarvis\.env
for p in (ENV_PATH, APPDATA_ENV):
    if p.exists():
        load_dotenv(p)
        break

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("JARVIS_MODEL", "claude-haiku-4-5-20251001")
WAKE_WORDS = ("jarvis", "hey jarvis")
ASSISTANT_NAME = "Jarvis"
USER_NAME = os.getenv("JARVIS_USER", "Sir")
