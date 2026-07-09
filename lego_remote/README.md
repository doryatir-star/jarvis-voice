# LEGO Remote

A small Flutter app that scans for a LEGO Bluetooth LE hub (SPIKE Prime,
SPIKE Essential, Powered Up, Control+) and lets you drive a two-motor robot
car with an on-screen joystick or a D-pad.

This is a standalone app, separate from the Jarvis voice assistant in the
rest of this repo.

## Setup

1. Install the [Flutter SDK](https://docs.flutter.dev/get-started/install) (stable channel).
2. From this folder:
   ```bash
   flutter pub get
   ```
3. Connect an Android or iOS device (or start an emulator/simulator — note
   Bluetooth doesn't work in most simulators/emulators, so a real device is
   recommended), then:
   ```bash
   flutter run
   ```

## Using it

1. Power on the LEGO hub so it starts advertising (button light on).
2. Open the app — it asks for Bluetooth/location permission, then scans.
3. Tap your hub in the list to connect.
4. Drive with the joystick (drag) or tap the icon in the top-right to
   switch to D-pad buttons. The red STOP button always cuts power
   immediately, and motors stop automatically if you background the app or
   lose connection.

## If your hub isn't found / doesn't drive correctly

The app assumes a modern LEGO hub speaking **LWP3** (LEGO Wireless Protocol
v3) — SPIKE Prime/Essential, Powered Up, and Control+ hubs all use it. All
of the protocol logic lives in `lib/ble/lwp3_hub.dart`:

- If your hub is an older **WeDo 2.0 Smart Hub**, it does not speak LWP3 —
  it uses a different, older Bluetooth GATT service. You'd need to swap the
  service/characteristic UUIDs and message format in `lwp3_hub.dart` for
  the WeDo 2.0 protocol.
- If your motors are attached to ports other than the default (port 0 =
  left, port 1 = right), pass `leftPort`/`rightPort` to
  `Lwp3Hub.setMotorPower` from `lib/screens/remote_screen.dart`, or attach
  the motors to the hub's A and B ports.

## Project layout

```
lib/
  ble/
    lwp3_hub.dart        LEGO Wireless Protocol v3 encode/decode + hub state
    hub_connection.dart  BLE scanning, permissions, connect/disconnect
  screens/
    scan_screen.dart     Lists nearby hubs, connect
    remote_screen.dart   Joystick/D-pad driving screen
  widgets/
    joystick.dart        Draggable joystick + tank-drive mixing
    dpad_controls.dart   Forward/back/left/right/stop buttons
    status_bar.dart      Connection + battery indicator
```
