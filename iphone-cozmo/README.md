# Control Cozmo from your iPhone — no computer needed

`cozmo_control.py` is a single file that drives a real Cozmo directly from
your iPhone, using only Python's standard library. No Mac, no Xcode, no
App Store app to buy from us, no `pip install` — you paste one file into
an existing on-device Python app and run it.

## Why this exists

The [`ios-cozmo-app/`](../ios-cozmo-app/) in this repo is a *native* iOS
app, but building and installing it requires a Mac with Xcode — there's no
way around that for a native app. If you only have an iPhone, that path is
closed to you. This is the alternative: instead of a native app, you run
a Python **script**, inside a Python **app** that's already on the App
Store.

## What you need

1. **An on-device Python app** from the App Store — any of these work,
   since this script only uses the standard library (no third-party
   packages to install):
   - **Pythonista 3** (paid, ~$10) — the most mature option, recommended.
   - **Pyto** (free) or **a-Shell** (free) — should also work.
2. **Cozmo**, obviously.

## Setup

1. Buy/install one of the apps above.
2. Put Cozmo on his charger to wake him up.
3. Raise and lower his lift with your hand — his screen shows a Wi-Fi
   network name and password.
4. In **iOS Settings > Wi-Fi**, join *that* network with your iPhone (not
   your home Wi-Fi — Cozmo's own hotspot usually has no internet, and
   that's fine, you don't need internet for this).
5. Open your Python app, create a new script, and paste in the entire
   contents of `cozmo_control.py`.
6. Run it.

## Using it

You'll see:
```
Connecting to Cozmo...
Sent RESET, waiting for Cozmo...
Connected -- waiting for firmware/body info...
Got firmware signature -- enabling motors.
Got body info -- initializing.
Cozmo ready!

Cozmo is ready! Type naturally -- "go forward", "can you turn left", "look up", "tell me a joke" -- or 'quit' to disconnect.
Movement: forward/backward, left/right, spin, stop, look up/down/straight, lift up/down, lights green/red/blue/white/off.
Chat: jokes, time, date, coin flip, dice, basic math, small talk (all offline -- no internet out here on Cozmo's own Wi-Fi).
> 
```
Talk to it naturally — "can you turn left", "go forward", "tell me a joke" all work, not just exact phrases. Type `quit` to disconnect.

Real movement commands (drive/turn/head/lift/lights) actually move Cozmo. Everything else — jokes, time, date, coin flips, dice, basic math, small talk — is answered by a small offline personality built into the script itself. It can't look anything up online (see below for why), so questions outside that list get an honest "I don't know that one" instead of a made-up answer.

**Keep the app open and your screen on.** iOS suspends apps that aren't
on screen, which stops the keep-alive ping Cozmo expects — if you lock
your phone or switch apps, he'll disconnect.

## Why you should trust this more than the native iOS app

Both `cozmo_control.py` and [`ios-cozmo-app/`](../ios-cozmo-app/)
reimplement the same undocumented, reverse-engineered Cozmo Wi-Fi
protocol (there's no official spec — Anki/Digital Dream Labs never
published one). The Swift app was written completely blind, with no Mac,
Xcode, or Cozmo available to test against.

This file is different: every packet it puts on the wire (`RESET`,
`DriveWheels`, `SetHeadAngle`, `SetLiftHeight`, `Enable`, `SetOrigin`,
`SyncTime`, backpack lights, `Ping`) was checked byte-for-byte against
[`pycozmo`](https://github.com/zayfod/pycozmo) — a real, working,
community-maintained Cozmo client — before being written here. That
check is a permanent part of this repo's test suite:
[`tests/test_cozmo_control_protocol.py`](../tests/test_cozmo_control_protocol.py).
Run it yourself with `pip install pycozmo` then
`python -m unittest tests.test_cozmo_control_protocol -v` — every wire
format claim this file makes is verified there, not just asserted.

That doesn't guarantee it'll work against your specific Cozmo's firmware
(hardware handshakes can still surprise you), but it's meaningfully more
trustworthy than code nobody could check against a reference at all.

## If it won't connect

1. Double-check your iPhone's Wi-Fi is joined to Cozmo's own network, not
   your home Wi-Fi.
2. Make sure Cozmo is actually awake (on his charger, lift raised and
   lowered once — his screen should be showing something, not asleep).
3. If "Sent RESET, waiting for Cozmo..." never progresses past that line
   within 8 seconds, the script gives up and tells you so — try again
   (Wi-Fi handshakes to Cozmo's own access point can be flaky the first
   time you join).
4. This has not been tested against real hardware (no Cozmo was available
   while building this) — if something's still wrong, the encode/decode
   logic is short enough (under 150 lines) to read end to end.
