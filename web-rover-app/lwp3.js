// LEGO Wireless Protocol 3.0 (LWP3) — the protocol LEGO's stock Powered
// Up/BOOST hub firmware speaks natively over Bluetooth LE. No Pybricks or
// custom firmware needed; this is the same protocol the official LEGO apps
// use. Byte layouts checked against LEGO's official protocol docs
// (github.com/LEGO/lego-ble-wireless-protocol-docs) and node-poweredup's
// real, shipped implementation (github.com/nathankellenicki/node-poweredup).

const HUB_SERVICE_UUID = '00001623-1212-efde-1623-785feabcd123';
const HUB_CHARACTERISTIC_UUID = '00001624-1212-efde-1623-785feabcd123';

const PORT = { A: 0x00, B: 0x01, C: 0x02, D: 0x03 };

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
 * is the "power" mode basic motors — including the Move Hub's built-in
 * tread motors — expose via WriteDirectModeData. */
function writeDirectModeDataPower(port, power) {
  const powerByte = (power < 0 ? 256 + power : power) & 0xff;
  const body = [port, STARTUP_AND_COMPLETION, SUBCOMMAND_WRITE_DIRECT_MODE_DATA, 0x00, powerByte];
  return withHeader(MESSAGE_TYPE_PORT_OUTPUT_COMMAND, body);
}

/** Move a motor to an absolute angle in degrees. "Absolute" is relative to
 * wherever the motor's internal zero position was when the hub powered
 * on — for predictable head/claw centering, power the hub on with the
 * head/claw already roughly centered. */
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
 * plugged into or unplugged from an external port). */
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

/** Parses a hex string like "0a0081020111010064" (spaces allowed, no 0x
 * prefix) into raw bytes, for the Console tab's "raw" command. */
function hexToBytes(str) {
  const clean = str.replace(/\s+/g, '');
  if (clean.length === 0 || clean.length % 2 !== 0) return null;
  const bytes = new Uint8Array(clean.length / 2);
  for (let i = 0; i < clean.length; i += 2) {
    const byte = parseInt(clean.substr(i, 2), 16);
    if (Number.isNaN(byte)) return null;
    bytes[i / 2] = byte;
  }
  return bytes;
}
