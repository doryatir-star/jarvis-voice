# J.A.R.V.I.S. — Voice Assistant for Windows

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

## Rover setup (optional)

If your Jarvis robot is built on a **LEGO BOOST Move Hub** (the hub from set 17101), you can drive it by voice — no firmware flashing needed, it uses LEGO's stock Bluetooth protocol.

1. Wire two motors into the hub's external ports (C/D) for the claw and the head — the two built-in motors already drive the tank treads.
2. Power on the hub (press its button) and run `python calibrate_ports.py` once. It figures out which port is the claw vs. the head, and which way each tread motor spins, then saves the answers to `.env`.
3. Run Jarvis as usual — say "Jarvis, move forward", "turn left", "turn your head right", "open the claw", "stop the rover", etc. The **ROVER** panel in the HUD shows connection status.
4. If the hub won't connect, pair it once with the official LEGO BOOST/Powered Up app to make sure it's on its original firmware, then try again.

Config options live in `.env` (see `.env.example`) — hub name/MAC, port assignments, drive speed/duration, and motor-polarity flags.

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
