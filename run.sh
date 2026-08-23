#!/usr/bin/env bash
# Sets up a virtualenv (first run only) and launches Jarvis on Linux/Ubuntu.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[Jarvis] Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f ".venv/.installed" ]; then
    echo "[Jarvis] Installing dependencies..."
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    touch .venv/.installed
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "[Jarvis] Created .env — edit it to add your ANTHROPIC_API_KEY for smart mode."
fi

python main.py
