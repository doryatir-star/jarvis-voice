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
3b. **Voice tab**: say **"Hey Jarvis"** then a command — "move forward",
   "turn left", "open the claw", "grab it", "stop", etc. — and it acts and
   speaks a confirmation back.
   **This only works on a computer with Chrome/Edge, NOT on iPhone.** Apple
   only allows speech recognition in Safari, and Safari can't do Bluetooth,
   so no iPhone browser can do voice + hub together. In Bluefy the Voice tab
   detects this and disables itself (with a note) so it can't grab the mic —
   earlier it would grab the mic and that dropped the Bluetooth connection.
   On iPhone, use the Controller buttons.
3c. **Experimental "Hold to talk"** (shown on the Voice tab when normal voice
   is blocked, i.e. on iPhone): uses an offline in-browser voice engine
   (Whisper, ~40 MB one-time download) instead of Apple's blocked one, as
   push-to-talk — hold the button, speak, release. The mic is opened only
   while held and fully released after, and the app tries to reconnect the
   hub if the mic drop occurs. **It may still not work on iPhone** — if
   opening the mic severs Bluetooth in Bluefy, the command may not reach the
   hub. The Voice tab log prints diagnostics (whether the mic dropped the
   hub, whether reconnect worked) so you can see exactly what happened.
3d. **Code tab**: write a real program (JavaScript) to control the rover, then
   Run. This works fine on iPhone (typing + Bluetooth, no microphone). You get
   real loops, variables and conditions. Building blocks (most need `await`):
   `forward(sec)`, `backward(sec)`, `left(sec)`, `right(sec)`,
   `arc(left%, right%, sec)` (curves/spins with independent wheels),
   `setMotors(left%, right%)`, `setSpeed(%)`,
   `headLeft()`, `headRight()`, `headCenter()`, `head(degrees)`,
   `clawOpen()`, `clawClose()`, `light("red")` (off/pink/purple/blue/
   lightblue/cyan/green/yellow/orange/red/white), `stop()`, `wait(sec)`,
   `repeat(n, fn)`, `random(min, max)`, `log(...)`. There's also an
   **Examples** menu (Square, Spin, Zigzag, Curvy loop, Wiggle head, Light
   show, Random walk, Grab and carry) to load and remix. Connect the hub
   first; Stop halts a running script; your script is saved on the device.
   Example:

   ```js
   for (let i = 0; i < 4; i++) {
     await forward(1);
     await left(0.6);
   }
   await clawClose();
   log("Done!");
   ```

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
