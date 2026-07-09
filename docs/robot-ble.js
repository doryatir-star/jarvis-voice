// robot-ble.js — LEGO Wireless Protocol 3.0 (LWP3) client over Web Bluetooth.
// Works with Powered Up / Technic Control+ / BOOST / SPIKE hubs, which all
// speak the same open LWP3 protocol: https://lego.github.io/lego-ble-wireless-protocol-docs/
window.RobotBLE = (function () {
  const SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123";
  const CHAR_UUID = "00001624-1212-efde-1623-785feabcd123";

  // Best-effort allowlist of known LPF2/LWP3 motor I/O Type IDs, used to guess
  // which attached ports are drive motors. The UI lets the user override the
  // guess, since not every hub/motor combination is covered here.
  const MOTOR_TYPE_IDS = new Set([
    0x01, 0x02, // WeDo / System train motor
    0x26, 0x27, // Powered Up medium motor, Move Hub internal motor
    0x2e, 0x2f, // Technic Large/XL Linear Motor (Control+)
    0x41, 0x42, // SPIKE medium / large angular motor
    0x49, 0x4b, // SPIKE Essential motors
  ]);

  let device = null, server = null, char = null;
  const ports = new Map(); // portId -> ioTypeId
  let leftPort = null, rightPort = null;
  const listeners = {};

  function on(type, fn) {
    (listeners[type] = listeners[type] || []).push(fn);
  }
  function emit(type, data) {
    (listeners[type] || []).forEach((fn) => fn(data));
  }

  function portLabel(portId) {
    return portId < 4 ? String.fromCharCode(65 + portId) : "#" + portId;
  }

  function guessMotorPorts() {
    const motors = [...ports.entries()]
      .filter(([, typeId]) => MOTOR_TYPE_IDS.has(typeId))
      .sort((a, b) => a[0] - b[0])
      .map(([portId]) => portId);
    if (leftPort === null || !ports.has(leftPort)) leftPort = motors[0] ?? null;
    if (rightPort === null || !ports.has(rightPort)) rightPort = motors[1] ?? motors[0] ?? null;
  }

  function emitStatus(connected) {
    emit("status", {
      connected,
      name: device && device.name,
      ports: [...ports.entries()].map(([portId, typeId]) => ({
        portId, typeId, label: portLabel(portId), isMotor: MOTOR_TYPE_IDS.has(typeId),
      })),
      leftPort, rightPort,
    });
  }

  async function send(bytes) {
    if (!char) return;
    const payload = new Uint8Array(bytes.length + 1);
    payload[0] = bytes.length + 1; // LWP3 length byte includes itself
    payload.set(bytes, 1);
    await char.writeValue(payload);
  }

  function onNotify(ev) {
    const bytes = new Uint8Array(ev.target.value.buffer);
    const msgType = bytes[2];
    if (msgType === 0x04) { // Hub Attached I/O
      const portId = bytes[3], event = bytes[4];
      if (event === 0x01) ports.set(portId, bytes[5] | (bytes[6] << 8)); // physical attach
      else if (event === 0x00) ports.delete(portId); // detach
      // event 0x02 (virtual/combined port) is ignored — we drive real ports individually
      guessMotorPorts();
      emitStatus(true);
    } else if (msgType === 0x01 && bytes[3] === 0x06 && bytes[4] === 0x06) {
      emit("battery", bytes[5]); // Hub Properties: Battery Voltage, Operation=Update
    }
  }

  function onDisconnected() {
    ports.clear();
    leftPort = rightPort = null;
    emitStatus(false);
  }

  async function connect() {
    device = await navigator.bluetooth.requestDevice({ filters: [{ services: [SERVICE_UUID] }] });
    device.addEventListener("gattserverdisconnected", onDisconnected);
    server = await device.gatt.connect();
    const service = await server.getPrimaryService(SERVICE_UUID);
    char = await service.getCharacteristic(CHAR_UUID);
    await char.startNotifications();
    char.addEventListener("characteristicvaluechanged", onNotify);
    ports.clear();
    leftPort = rightPort = null;
    emitStatus(true);
    await send([0x00, 0x01, 0x06, 0x02]); // subscribe to battery % updates
  }

  async function disconnect() {
    try { await stop(); } catch (e) {}
    try { if (char) await char.stopNotifications(); } catch (e) {}
    try { if (device && device.gatt.connected) device.gatt.disconnect(); } catch (e) {}
  }

  async function setMotorPower(portId, speed) {
    if (portId === null || portId === undefined) return;
    const clamped = Math.max(-100, Math.min(100, Math.round(speed)));
    const signed = clamped < 0 ? 256 + clamped : clamped;
    // Port Output Command, SubCommand WriteDirectModeData, Mode 0 (power/speed) —
    // the one motor-control encoding supported across LPF2/LWP3 motor types.
    await send([0x00, 0x81, portId, 0x11, 0x51, 0x00, signed]);
  }

  async function driveMotors(left, right) {
    await Promise.all([setMotorPower(leftPort, left), setMotorPower(rightPort, right)]);
  }

  async function stop() {
    await driveMotors(0, 0);
  }

  function setLeftPort(portId) { leftPort = portId; emitStatus(!!char); }
  function setRightPort(portId) { rightPort = portId; emitStatus(!!char); }

  return {
    get isSupported() { return !!navigator.bluetooth; },
    on, connect, disconnect, driveMotors, stop, setLeftPort, setRightPort,
  };
})();
