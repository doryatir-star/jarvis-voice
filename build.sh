#!/usr/bin/env bash
# Builds a standalone "Jarvis" binary on Linux/Ubuntu with PyInstaller and
# installs a desktop launcher (Show Applications / activities search).
set -e
cd "$(dirname "$0")"

VENV=".buildvenv"

echo "=== Jarvis build ==="

if [ ! -x "$VENV/bin/python" ]; then
    echo "[build] Creating virtualenv at $VENV ..."
    python3 -m venv "$VENV"
fi

PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "[build] Upgrading pip..."
"$PY" -m pip install --upgrade pip >/dev/null

echo "[build] Installing dependencies..."
"$PIP" install -r requirements.txt
"$PIP" install pyinstaller pillow

echo "[build] Generating icon..."
"$PY" make_icon.py

echo "[build] Cleaning previous build..."
rm -rf build dist Jarvis.spec

echo "[build] Running PyInstaller (takes a minute) ..."
"$VENV/bin/pyinstaller" \
  --noconfirm --onefile \
  --name Jarvis \
  --icon jarvis.png \
  --add-data "jarvis.png:." \
  --collect-all speech_recognition \
  --collect-all pyaudio \
  --collect-all pyttsx3 \
  --collect-all bleak \
  --collect-all pylgbst \
  main.py

if [ ! -f "dist/Jarvis" ]; then
    echo
    echo "[build] FAILED — see errors above."
    exit 1
fi

chmod +x dist/Jarvis

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons"
mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"

cp dist/Jarvis "$BIN_DIR/jarvis"
cp jarvis.png "$ICON_DIR/jarvis.png"

cat > "$APPS_DIR/jarvis.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Jarvis
Comment=Voice assistant
Exec=$BIN_DIR/jarvis
Icon=$ICON_DIR/jarvis.png
Terminal=false
Categories=Utility;
EOF
chmod +x "$APPS_DIR/jarvis.desktop"

echo
echo "=== SUCCESS ==="
echo "Installed to $BIN_DIR/jarvis — search for 'Jarvis' in your app launcher,"
echo "or run it directly with: $BIN_DIR/jarvis"
echo "(Optional) create ~/.config/jarvis/.env with ANTHROPIC_API_KEY=... for smart mode."
echo
echo "Make sure $HOME/.local/bin is on your PATH if you want to run 'jarvis' from a terminal."
