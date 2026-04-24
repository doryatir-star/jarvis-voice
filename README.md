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
