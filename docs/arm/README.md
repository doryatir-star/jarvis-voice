# LEGO Robotic Arm — build guide + wiring tester

A step-by-step guide for building a simple 2-motor robotic arm (base
rotation + shoulder lift) around the LEGO Powered Up **Technic Large Hub,
element 88016**, plus a small phone-usable page to test the wiring over
Bluetooth once it's built. Follows the same no-build-step, plain
HTML/CSS/JS convention as `docs/rover/` in this repo.

## Getting this page onto your phone

This lives at `docs/arm/` so GitHub Pages (which already serves this
repo's `docs/` folder) picks it up automatically once this is on the
repo's default branch. If GitHub Pages is enabled for this repo, the URL
will be:

    https://doryatir-star.github.io/jarvis-voice/arm/

If that link 404s, GitHub Pages likely isn't turned on yet — enable it in
the repo's Settings > Pages (source: deploy from a branch, folder:
`/docs`).

## Using it

1. **Guide tab**: the parts checklist and build steps for the arm. Checkbox
   state is saved on your device (`localStorage`) so it's still checked off
   next time you open the page.
2. **Wiring tab**: which port each motor goes into (A = base, B = shoulder
   by default — swap this in Settings if you wire them the other way), plus
   notes on cable slack and powering on the hub.
3. **Test tab**: once the arm is wired up, connect over Bluetooth and use
   the Base/Shoulder buttons to jog each motor, or the Nudge buttons to
   figure out which port is which before you finish the build. On iPhone,
   open this page in the **Bluefy** app (Safari blocks Web Bluetooth
   entirely); on desktop use Chrome or Edge.
4. **Settings tab**: which port is base vs. shoulder, motor speed, and how
   long a tap moves before auto-stopping. Saved on your device between
   visits.

## Notes

- Uses the same stock LEGO LWP3 Bluetooth protocol as `docs/rover/` — no
  firmware flashing. The connection code (`arm-hub.js`) is hub-agnostic
  (generic LEGO Wireless Protocol service UUID, `acceptAllDevices: true`),
  so it works against the 88016 hub without modification.
- This app only assumes 2 motors (base + shoulder). If you add more motors
  later (e.g. an elbow or a powered gripper), the hub has 6 ports total
  (A–F) — `lwp3.js` already defines all six, this app's UI just doesn't
  expose the extra ones yet.
