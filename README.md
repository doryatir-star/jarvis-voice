# J.A.R.V.I.S. — Voice Assistant for Windows

**▶ [Open the Robotic Arm Guide](https://doryatir-star.github.io/jarvis-voice/arm/)** · **▶ [Open the Rover Controller](https://doryatir-star.github.io/jarvis-voice/rover/)**

A futuristic desktop AI assistant. Say **"Jarvis, …"** and it runs the command — opens any app, controls volume, searches the web, and more.

## Download

Grab the latest **`Jarvis.exe`** from the [Releases page](../../releases/latest) and double-click it. No install, no folder, no Python needed.

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
- **Real Anki Cozmo control (optional)** — drive an actual Cozmo robot by voice over Wi-Fi: "Jarvis, move forward / turn left / look up / lift up / green lights / stop". See [Cozmo setup](#cozmo-setup-optional) below.

## Rover setup (optional)

If your Jarvis robot is built on a **LEGO BOOST Move Hub** (the hub from set 17101), you can drive it by voice — no firmware flashing needed, it uses LEGO's stock Bluetooth protocol.

1. Wire two motors into the hub's external ports (C/D) for the claw and the head — the two built-in motors already drive the tank treads.
2. Power on the hub (press its button) and run `python calibrate_ports.py` once. It figures out which port is the claw vs. the head, and which way each tread motor spins, then saves the answers to `.env`.
3. Run Jarvis as usual — say "Jarvis, move forward", "turn left", "turn your head right", "open the claw", "stop the rover", etc. The **ROVER** panel in the HUD shows connection status.
4. If the hub won't connect, pair it once with the official LEGO BOOST/Powered Up app to make sure it's on its original firmware, then try again.

Config options live in `.env` (see `.env.example`) — hub name/MAC, port assignments, drive speed/duration, and motor-polarity flags.

## Cozmo setup (optional)

Jarvis can also drive a real **Anki / Digital Dream Labs Cozmo** robot, using [`pycozmo`](https://github.com/zayfod/pycozmo) — a pure-Python reimplementation of Cozmo's Wi-Fi protocol. No phone, no official Cozmo app, no SDK tether needed.

1. `pip install -r requirements.txt` (pulls in `pycozmo`), then run `pycozmo_resources.py download` once to fetch Cozmo's animation assets.
2. Put Cozmo on his charger to wake him, then raise and lower his lift — his screen shows a Wi-Fi network name and password.
3. Connect **this PC's** Wi-Fi to that network (Cozmo runs his own access point; your PC can't be on your home Wi-Fi and Cozmo's at the same time).
4. Set `ROBOT_TYPE=cozmo` in `.env` (copy from `.env.example` if you don't have one yet), then run Jarvis as usual.
5. Say "Jarvis, move forward", "turn left", "look up", "lift up", "green lights", "stop" etc. The **COZMO** panel in the HUD shows connection status.

Cozmo doesn't have a claw, so claw commands don't apply — instead he has a lift (`lift up` / `lift down`), backpack lights (`green lights` / `red lights` / `blue lights` / `white lights` / `lights off`), and animation clips (`play animation <exact clip name>` — find clip names by printing `pycozmo.Client().anim_names` after `load_anims()`, in a small standalone script). Drive/turn/stop/head commands work the same as the LEGO rover.

Config options (`COZMO_DRIVE_SPEED`, `COZMO_DRIVE_SECONDS`, `COZMO_TURN_SPEED`, `COZMO_TURN_SECONDS`) live in `.env` — see `.env.example`.

**Prefer your phone?** [`ios-cozmo-app/`](ios-cozmo-app/) is a native iPhone app that drives Cozmo directly — no PC needed. See its README for setup (built in Xcode) and important caveats — it reimplements Cozmo's undocumented Wi-Fi protocol and hasn't been tested against a Mac, real iPhone, or real Cozmo.

## Requirements

- Windows 10 or 11
- Internet connection (speech recognition uses Google's free public API)
- Microphone

## First launch

- Windows SmartScreen may show "unknown publisher" — click **More info → Run anyway**. The app is unsigned.
- First launch unpacks in ~10–15 seconds.
- If it doesn't hear you, use the mic dropdown to pick a different input device.

## Privacy

Speech is sent to Google's public speech endpoint. No telemetry, no accounts, no stored data. A small diagnostic log lives at `%TEMP%\jarvis_voice.log`.

## Build from source

```bat
git clone <this repo>
cd Jarvis
build.bat
```

Produces `Jarvis.exe` on your Desktop.

## License

MIT
