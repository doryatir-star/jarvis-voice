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

## Want an actual AI deciding what Cozmo does? Use `cozmo_ai.py` instead

`cozmo_control.py`'s "brain" is just pattern matching — it recognizes
phrases and runs fixed logic. `cozmo_ai.py` is different: it sends what
you say to **Claude**, and Claude itself decides whether to reply, move
Cozmo, or both — real reasoning, not a lookup table.

This needs two things `cozmo_control.py` doesn't:

1. **An Anthropic API key** — https://console.anthropic.com. This is a
   real account with pay-as-you-go billing (not free, not a
   subscription) — typically a fraction of a cent per exchange with the
   default model, but real money nonetheless.
2. **Your iPhone's cellular data turned on.** Cozmo's Wi-Fi has no
   internet, but Claude needs internet to think. As long as cellular
   data is on, iOS automatically routes internet traffic (Claude) over
   cellular while Wi-Fi keeps talking to Cozmo — you don't have to
   switch networks back and forth, just don't have cellular data turned
   off.

Setup:
1. Get an API key from the link above.
2. Paste **both** `cozmo_control.py` and `cozmo_ai.py` into your Python
   app (`cozmo_ai.py` imports the other one — both files need to be
   there).
3. Open `cozmo_ai.py` and paste your key into the `API_KEY = ` line near
   the top, replacing `"PASTE_YOUR_KEY_HERE"`.
4. Run `cozmo_ai.py` instead of `cozmo_control.py`. Everything else
   (waking Cozmo, joining his Wi-Fi) is identical.

It uses raw HTTPS calls to Claude's API, not the official `anthropic`
Python package — that package depends on compiled code that no on-device
iOS Python app can install (iOS blocks apps from loading unsigned native
code, no exceptions). The request format matches Anthropic's public API
documentation exactly; see the module's own docstring for details.

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
