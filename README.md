# J.A.R.V.I.S. — Voice Assistant for Windows & Ubuntu

**▶ [Open the Robotic Arm Guide](https://doryatir-star.github.io/jarvis-voice/arm/)** · **▶ [Open the Rover Controller](https://doryatir-star.github.io/jarvis-voice/rover/)**

A futuristic desktop AI assistant. Say **"Jarvis, …"** and it runs the command — opens any app, controls volume, searches the web, and more.

## Download (Windows)

Grab the latest **`Jarvis.exe`** from the [Releases page](../../releases/latest) and double-click it. No install, no folder, no Python needed.

## Run on Ubuntu

1. Install the system packages Jarvis needs to talk and listen:

   ```bash
   sudo apt update
   sudo apt install python3-venv python3-pip portaudio19-dev espeak \
       xclip xdotool wmctrl playerctl brightnessctl
   ```

   - `portaudio19-dev` — required to build `pyaudio` (microphone input)
   - `espeak` — the offline voice `pyttsx3` speaks with
   - `xclip` — clipboard read/write ("copy that", password generator, etc.)
   - `xdotool` / `wmctrl` — window control, hotkeys, "type this"
   - `playerctl` / `brightnessctl` — media keys / screen brightness (optional; those commands just no-op without them)

2. Clone the repo and run it:

   ```bash
   git clone <this repo>
   cd jarvis-voice
   ./run.sh
   ```

   `run.sh` creates a virtualenv, installs the Python dependencies, copies `.env.example` to `.env` on first run, and starts Jarvis.

3. (Optional) build a standalone binary with its own app-launcher entry:

   ```bash
   ./build.sh
   ```

   Installs `~/.local/bin/jarvis` plus a `Jarvis` entry in your application menu.

Ubuntu notes: volume/mute/media keys use `pactl`/`playerctl` (PulseAudio/PipeWire — both ship on stock Ubuntu), lock/suspend/shutdown/restart go through `loginctl`/`systemctl` (no `sudo` needed for your own session), and the app-launcher command ("Jarvis, open Blender") indexes `.desktop` files from `/usr/share/applications` and `~/.local/share/applications` instead of the Windows Start Menu.

## Features

- **Voice control (always listening)** — wake word "Jarvis" (plus common mishears)
- **Opens anything on your PC** — Start Menu shortcuts, Desktop shortcuts, Microsoft Store apps (Roblox, Discord, Blender, Steam games, etc.)
- **Websites** — "Jarvis, open YouTube / Gmail / Netflix / Spotify / Roblox"
- **Media & system** — volume, brightness, mute, play/pause, lock, sleep, shutdown, restart, screenshot, empty recycle bin, battery level, time/date
- **Folders** — "open Downloads / Documents / Recycle Bin"
- **Smart Q&A without any API key** — DuckDuckGo + Wikipedia fallback
- **Futuristic HUD** — arc-reactor animation, live audio level meter, microphone picker
- **LEGO rover control (optional)** — drives a LEGO BOOST Move Hub robot over Bluetooth: "Jarvis, move forward / move backward / turn left / turn right / turn your head left / open the claw / stop the rover". See [Rover setup](#rover-setup-optional) below.
- **LEGO robotic arm build guide (new!)** — a phone-friendly step-by-step guide for building a 3-motor robotic arm (base + shoulder + gripper) around the Powered Up Technic Large Hub (element **88016**), plus a Bluetooth wiring-tester page. Source in [`docs/arm/`](docs/arm/) — **[open the live guide here](https://doryatir-star.github.io/jarvis-voice/arm/)**.

## Rover setup (optional)

If your Jarvis robot is built on a **LEGO BOOST Move Hub** (the hub from set 17101), you can drive it by voice — no firmware flashing needed, it uses LEGO's stock Bluetooth protocol.

1. Wire two motors into the hub's external ports (C/D) for the claw and the head — the two built-in motors already drive the tank treads.
2. Power on the hub (press its button) and run `python calibrate_ports.py` once. It figures out which port is the claw vs. the head, and which way each tread motor spins, then saves the answers to `.env`.
3. Run Jarvis as usual — say "Jarvis, move forward", "turn left", "turn your head right", "open the claw", "stop the rover", etc. The **ROVER** panel in the HUD shows connection status.
4. If the hub won't connect, pair it once with the official LEGO BOOST/Powered Up app to make sure it's on its original firmware, then try again.

Config options live in `.env` (see `.env.example`) — hub name/MAC, port assignments, drive speed/duration, and motor-polarity flags.

## Requirements

- Windows 10/11, or Ubuntu 22.04+ (other Linux distros likely work too — see [Run on Ubuntu](#run-on-ubuntu) for the system packages)
- Internet connection (speech recognition uses Google's free public API)
- Microphone

## First launch

- Windows SmartScreen may show "unknown publisher" — click **More info → Run anyway**. The app is unsigned.
- First launch unpacks in ~10–15 seconds.
- If it doesn't hear you, use the mic dropdown to pick a different input device.

## Privacy

Speech is sent to Google's public speech endpoint. No telemetry, no accounts, no stored data. A small diagnostic log lives at `%TEMP%\jarvis_voice.log` on Windows, or `/tmp/jarvis_voice.log` on Linux.

## Build from source

**Windows:**

```bat
git clone <this repo>
cd Jarvis
build.bat
```

Produces `Jarvis.exe` on your Desktop.

**Ubuntu:**

```bash
git clone <this repo>
cd jarvis-voice
./build.sh
```

Installs `~/.local/bin/jarvis` and adds a `Jarvis` entry to your application menu. See [Run on Ubuntu](#run-on-ubuntu) for the required system packages.

## License

MIT
