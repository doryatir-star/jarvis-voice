# Cozmo Controller — iOS app

A native iPhone app to drive a real Anki / Digital Dream Labs **Cozmo**
robot directly over Wi-Fi — no PC, no official Cozmo app, no phone tether
to a computer. A manual controller (drive, head, lift, backpack lights)
plus a live traffic console for debugging.

**Read this before you get started — more than usual.** This code was
written without access to a Mac, Xcode, an iPhone, *or a real Cozmo* —
there was no way to compile, build, sign, or test any of it, and unlike a
simple Bluetooth command, Cozmo's Wi-Fi protocol is an undocumented,
reverse-engineered, stateful handshake with sequence numbers. Get one byte
of the handshake wrong and the *whole thing* silently fails to connect at
all — there's no small motor twitch to reassure you it's half-working. The
Console tab exists specifically to make that debugging possible: it shows
every raw byte sent and received, so if Cozmo never gets past "Connecting…"
you can compare the bytes here against `pycozmo`'s source
(https://github.com/zayfod/pycozmo) — the same reverse-engineered reference
this app's `CozmoProtocol.swift` was built from — or against the already
working Python desktop app's `cozmo_hub.py` in the repo root.

## Why a native app instead of a web app

Cozmo doesn't use Bluetooth. He creates his own Wi-Fi hotspot, and talks a
custom framed protocol over plain UDP (port 5551) — not HTTP, not
WebSocket, nothing a browser's JavaScript can open. There is no way to do
this from a web page on iOS (or anywhere else). A native app using Apple's
`Network.framework` (raw UDP sockets) is the only way.

## What this app does NOT do

To keep this a buildable, debuggable first version, it deliberately leaves
out:
- **Animations** (`play_anim` on the Python side) — real animation
  playback streams keyframes decoded from Cozmo's binary asset files, a
  much bigger undertaking than manual control. Not implemented here.
- **Camera streaming.**
- **Full reliable delivery.** The real protocol has a sliding-window
  ack/retransmit system; this app sends each command once and relies on
  the fact that you're one Wi-Fi hop away from the robot. Good enough for
  a joystick-style controller — if a "stop" ever doesn't land, tap it
  again.

## Setup (do this in Xcode, on a Mac)

1. Open Xcode → **File → New → Project → iOS → App**. Product name
   "CozmoController", interface **SwiftUI**, language **Swift**.
2. Delete the auto-generated `ContentView.swift` Xcode created, then drag
   every `.swift` file from this folder (`CozmoController/`) into your new
   project (check "Copy items if needed").
3. Select your project in the navigator → your app target → **Info** tab →
   add a new key: **Privacy - Local Network Usage Description**
   (`NSLocalNetworkUsageDescription`) with a value like "Used to connect to
   your Cozmo robot over Wi-Fi." iOS will block the connection (and may
   show a permission prompt you need to allow) without this key.
4. Select your app target → **Signing & Capabilities** → under "Team",
   choose your own Apple ID (a free personal team works — no paid Apple
   Developer account needed to run on your own device, though the app will
   need re-signing from Xcode roughly every 7 days).
5. Plug your iPhone into the Mac, select it as the run destination, hit
   **Run**.

## Using the app

1. **Connect tab**: put Cozmo on his charger to wake him, raise and lower
   his lift — his screen shows a Wi-Fi network name and password. In iOS
   Settings, join **that** network with your iPhone (the "Open Wi-Fi
   Settings" button jumps you there). Come back and tap **Connect**.
2. Status should go Connecting… → Talking to Cozmo… → Connected. This
   whole handshake normally takes well under a second.
3. **Controller tab**: forward/backward/left/right/stop, head up/center/
   down, lift up/down, backpack lights (green/red/blue/white/off).
4. **Console tab**: a live log of every byte sent/received, plus a text box
   for typed commands: `forward`, `backward`, `left`, `right`, `stop`,
   `head up` / `head down` / `head center`, `lift up` / `lift down`,
   `lights <color>`, `connect`, `disconnect`, or `raw <hex bytes>` to send
   a hand-crafted frame (no spaces or `0x` prefix).
5. **Settings tab**: drive/turn speed (mm/s, Cozmo's hardware max is 200)
   and how long a drive/turn command runs before auto-stopping.

## If it won't connect

1. Confirm your iPhone's Wi-Fi is actually joined to Cozmo's network (not
   your home Wi-Fi) — check the Wi-Fi icon/name in iOS Settings.
2. Check the Console tab for a `->` line right after tapping Connect (the
   outgoing RESET frame). No `->` line at all means the UDP socket never
   became ready — check that you allowed the Local Network permission
   prompt (Settings → CozmoController → Local Network).
3. If you see `->` but never a `<-` reply, Cozmo either isn't listening on
   172.31.1.1:5551 (double check he's awake and you're on his network) or
   the RESET frame's bytes are malformed — compare against
   `CozmoFrame.encode`'s output for a RESET frame against pycozmo's
   `frame.py`.
4. If you see a `<-` reply but the app stays on "Connecting…", the frame
   decoder likely rejected it — check `CozmoProtocol.swift`'s `decode()`
   against the raw bytes logged.
5. If you get to "Talking to Cozmo…" but never "Cozmo ready", Cozmo may be
   sending packet IDs in an order or format this app doesn't expect (this
   is the part most likely to have drifted from Cozmo's actual current
   firmware, since it's the least-documented part of the handshake) —
   the Console log will show every packet ID byte the robot sends.
