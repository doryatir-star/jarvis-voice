# LEGO Rover Controller — iOS app

A native iPhone app to drive the same LEGO BOOST Move Hub rover as the
Windows Jarvis assistant, but from your phone: a manual controller (D-pad,
head, claw), a live Bluetooth traffic console, and port/speed settings.

**Read this before you get started.** This code was written without access
to a Mac, Xcode, or an iPhone — there was no way to compile, build, sign, or
test any of it. It's written carefully against CoreBluetooth (a stable,
long-standing Apple API) and LEGO's official published Bluetooth protocol,
but you should expect to do some of your own debugging — most likely small
Swift syntax fixes if API details drifted, and definitely some tuning of the
motor speed/power numbers once you see it move for real. The Console tab
(see below) exists specifically to make that debugging possible: it shows
every raw byte sent and received.

## Why a native app instead of a web app

On iPhone, Safari (and any web view) blocks the Web Bluetooth API entirely,
so a normal web page can't talk to the LEGO hub's Bluetooth. A native app
using Apple's CoreBluetooth framework is the only way to do this on iOS
without an extra third-party browser.

## What it uses instead of Pybricks

Same choice as the Windows app: the hub keeps its **stock LEGO firmware**.
This app speaks LEGO's own Bluetooth protocol (LWP3) directly — the same
protocol the official LEGO apps use — via Apple's CoreBluetooth framework.
No firmware flashing, no pairing with a special app first (though pairing
once with the official LEGO BOOST/Powered Up app is a good way to confirm
the hub is on stock firmware and healthy before trying this app).

## Setup (do this in Xcode, on a Mac)

1. Open Xcode → **File → New → Project → iOS → App**. Product name
   "RoverController", interface **SwiftUI**, language **Swift**.
2. Delete the auto-generated `ContentView.swift` Xcode created, then drag
   every `.swift` file from this folder (`RoverController/`) into your new
   project (check "Copy items if needed").
3. Select your project in the navigator → your app target → **Info** tab →
   add a new key: **Privacy - Bluetooth Always Usage Description**
   (`NSBluetoothAlwaysUsageDescription`) with a value like "Used to connect
   to your LEGO rover." iOS will crash the app on launch without this key.
4. Select your app target → **Signing & Capabilities** → under "Team",
   choose your own Apple ID (a free personal team works — no paid Apple
   Developer account needed to run on your own device, though the app will
   need re-signing from Xcode roughly every 7 days).
5. Plug your iPhone into the Mac, select it as the run destination, hit
   **Run**. First launch will prompt for Bluetooth permission — allow it.

## Using the app

- **Connect tab**: tap "Scan for hubs" (make sure the LEGO hub is powered on
  — press its button if it's asleep), tap the hub in the list to connect.
- **Controller tab**: forward/backward/left/right/stop, head left/center/
  right, claw open/close, and two "Nudge Port C/D" buttons to help you
  figure out which external port drives the claw vs. the head — watch which
  motor twitches, then set it correctly in the Settings tab.
- **Console tab**: a live log of every byte sent/received, plus a text box
  for typed commands: `forward`, `backward`, `left`, `right`, `stop`,
  `head left` / `head right` / `head center`, `claw open` / `claw close`,
  `scan`, or `raw <hex bytes>` to send a hand-crafted LWP3 message (no
  spaces or `0x` prefix, e.g. `raw 0a0081020111010064`).
- **Settings tab**: which port (C/D) is the claw vs. the head, drive speed,
  and how long a drive/turn command runs before auto-stopping.

## If a motor doesn't respond

1. Check the Console tab — does it show `-> ...` (bytes actually sent)? If
   not, the app isn't connected to the characteristic yet.
2. Check for `<- ...` lines (the hub talking back) — LEGO hubs send a
   feedback message after each command; silence there usually means the
   port number is wrong for that motor.
3. Use the "Nudge Port C/D" buttons on the Controller tab and the "Port
   attached" log lines in the Console tab to confirm which port has which
   motor, then fix the Claw/Head port assignment in Settings.
4. Compare the raw bytes being sent against LEGO's official protocol docs:
   github.com/LEGO/lego-ble-wireless-protocol-docs — the message format is
   documented in `LWP3.swift`'s comments.
