// LEGO Wireless Protocol 3.0 (LWP3) — the protocol LEGO's stock Powered Up
// hub firmware speaks natively over Bluetooth LE, including the Technic
// Large Hub (element 88016) this arm app targets. No Pybricks or custom
// firmware needed; this is the same protocol the official LEGO apps use.
// Byte layouts checked against LEGO's official protocol docs
// (github.com/LEGO/lego-ble-wireless-protocol-docs) and node-poweredup's
// real, shipped implementation (github.com/nathankellenicki/node-poweredup).
//
// Copied from docs/rover/lwp3.js — the protocol/service UUIDs and message
// encoding are identical across Powered Up hubs, only the port count
// differs (the Large Hub exposes 6 ports, A-F, vs. the Move Hub's 4).

const HUB_SERVICE_UUID = '00001623-1212-efde-1623-785feabcd123';
const HUB_CHARACTERISTIC_UUID = '00001624-1212-efde-1623-785feabcd123';

const PORT = { A: 0x00, B: 0x01, C: 0x02, D: 0x03, E: 0x04, F: 0x05 };

const END_STATE = { FLOAT: 0, HOLD: 126, BRAKE: 127 };

const MESSAGE_TYPE_PORT_OUTPUT_COMMAND = 0x81;
const MESSAGE_TYPE_HUB_ATTACHED_IO = 0x04;
// Startup/completion byte: high nibble = startup info (0x10 = execute
// immediately instead of queuing), low nibble = completion info
// (0x01 = send a feedback message back). 0x11 combines both.
const STARTUP_AND_COMPLETION = 0x11;
const SUBCOMMAND_WRITE_DIRECT_MODE_DATA = 0x51;
const SUBCOMMAND_GOTO_ABSOLUTE_POSITION = 0x0d;

function portName(port) {
  const found = Object.keys(PORT).find((k) => PORT[k] === port);
  return found || '0x' + port.toString(16);
}

function withHeader(messageType, body) {
  // Header is [length, hubID(0x00), messageType] + body. Only the
  // single-byte length form is implemented — fine here since every message
  // we send is well under the 127-byte escape threshold.
  const total = 3 + body.length;
  return new Uint8Array([total, 0x00, messageType, ...body]);
}

/** Continuous drive power for a single motor, -100..100 (0 = stop). Mode 0
 * is the "power" mode basic/angular motors expose via WriteDirectModeData. */
function writeDirectModeDataPower(port, power) {
  const powerByte = (power < 0 ? 256 + power : power) & 0xff;
  const body = [port, STARTUP_AND_COMPLETION, SUBCOMMAND_WRITE_DIRECT_MODE_DATA, 0x00, powerByte];
  return withHeader(MESSAGE_TYPE_PORT_OUTPUT_COMMAND, body);
}

/** Move a motor to an absolute angle in degrees. "Absolute" is relative to
 * wherever the motor's internal zero position was when the hub powered
 * on — for predictable behavior, power the hub on with the arm already
 * roughly in its rest position. */
function gotoAbsolutePosition(port, angle, speed, maxPower, endState) {
  const angleBytes = new Uint8Array(4);
  new DataView(angleBytes.buffer).setInt32(0, angle, true);
  const speedByte = (speed < 0 ? 256 + speed : speed) & 0xff;
  const body = [
    port, STARTUP_AND_COMPLETION, SUBCOMMAND_GOTO_ABSOLUTE_POSITION,
    ...angleBytes, speedByte, maxPower & 0xff, endState, 0x00,
  ];
  return withHeader(MESSAGE_TYPE_PORT_OUTPUT_COMMAND, body);
}

/** Parses a "Hub Attached I/O" notification (sent whenever a motor is
 * plugged into or unplugged from a port). */
function parseHubAttachedIO(bytes) {
  if (bytes.length < 5 || bytes[2] !== MESSAGE_TYPE_HUB_ATTACHED_IO) return null;
  const port = bytes[3];
  const event = bytes[4];
  if (event === 0x00) return { port, attached: false, ioTypeID: null };
  if (bytes.length < 7) return { port, attached: true, ioTypeID: null };
  const ioTypeID = bytes[5] | (bytes[6] << 8);
  return { port, attached: true, ioTypeID };
}

function toHex(bytes) {
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
}
