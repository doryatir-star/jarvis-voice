# LEGO Rover Controller — web app (for iPhone, no computer needed)

A phone-usable controller for the LEGO BOOST Move Hub rover that needs **no
Mac, no Xcode, no computer at all** — just installing one app from the App
Store on your iPhone. This exists specifically because the native Swift
app (`ios-rover-app/`) requires a Mac to build, which isn't an option if
you're iPhone-only.

Unlike the Swift app, this one has actually been run and checked (headless
Chromium, via Playwright) — page loads with no script errors, all tabs and
buttons work, and the console command parser was exercised. What's **not**
verified is the real Bluetooth connection to the hub itself, since that
needs a real iPhone, a real hub, and the Bluefy app — none of which exist
in the environment this was written in.

## Why not just Safari?

Safari (and every browser on iPhone, since they all use Apple's WebKit)
blocks the Web Bluetooth API entirely. There is exactly one practical
workaround: **Bluefy**, a small third-party iOS browser built specifically
to support Web Bluetooth. Install it from the App Store, then open this
page in Bluefy instead of Safari.

## Getting this page onto your phone

This lives at `docs/rover/` specifically so GitHub Pages (which already
serves this repo's `docs/` folder) picks it up automatically once this is
on the repo's default branch. If GitHub Pages is enabled for this repo,
the URL will be:

    https://doryatir-star.github.io/jarvis-voice/rover/

If that link 404s, GitHub Pages likely isn't turned on yet for this repo —
turn it on in the repo's Settings > Pages (source: deploy from a branch,
folder: `/docs`), or ask for help getting it enabled.

## Using it

1. Open the hosted URL in **Bluefy** (not Safari).
2. **Connect tab**: tap "Scan & Connect" — the hub must be powered on
   (press its button if it's asleep). iOS will show its own Bluetooth
   picker; choose your hub.
3. **Controller tab**: forward/backward/left/right/stop, head left/center/
   right, claw open/close, and "Nudge Port C/D" to help identify which
   external port drives the claw vs. the head.
4. **Console tab**: a live log of every byte sent/received, plus a text
   box for typed commands: `forward`, `backward`, `left`, `right`, `stop`,
   `head left` / `head right` / `head center`, `claw open` / `claw close`,
   `scan`, or `raw <hex bytes>` (no spaces needed, e.g.
   `raw 0a0081020111010064`) to send a hand-crafted LWP3 message.
5. **Settings tab**: which port (C/D) is the claw vs. the head, drive
   speed, and how long a drive/turn runs before auto-stopping. These are
   remembered on your phone (localStorage) between visits.

## If a motor doesn't respond

Same protocol as the Windows and iOS apps (LEGO's stock LWP3 Bluetooth
protocol — no firmware flashing). Check the Console tab: do you see `->`
(bytes sent) and `<-` (the hub replying)? If sending fails outright, the
connection likely dropped. If bytes are sent but nothing moves, use the
"Nudge Port C/D" buttons and the "Port ... attached" log lines to confirm
which port has which motor, then fix the assignment in Settings.
