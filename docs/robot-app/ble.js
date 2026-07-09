// ble.js — LEGO Wireless Protocol 3.0 (LWP3) client over Web Bluetooth.
// Works with Powered Up / Technic Control+ / BOOST / SPIKE hubs, which all
// speak the same open LWP3 protocol: https://lego.github.io/lego-ble-wireless-protocol-docs/
window.RobotBLE = (function () {
  const SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123";
  const CHAR_UUID = "00001624-1212-efde-1623-785feabcd123";
  const LAST_DEVICE_KEY = "robotapp.lastDeviceId";

  // Best-effort I/O Type ID tables. The UI lets the user re-pick ports
  // manually, since not every hub/motor/sensor combination is covered here.
  const MOTOR_TYPE_IDS = new Set([
    0x01, 0x02, // WeDo / System train motor
    0x26, 0x27, // Powered Up medium motor, Move Hub internal motor
    0x2e, 0x2f, // Technic Large/XL Linear Motor (Control+)
    0x41, 0x42, // SPIKE medium / large angular motor
    0x49, 0x4b, // SPIKE Essential motors
  ]);
  const LIGHT_TYPE_IDS = new Set([0x08, 0x17]); // Light, built-in Hub RGB Light

  let device = null, server = null, char = null;
  const ports = new Map(); // portId -> ioTypeId
  let leftPort = null, rightPort = null, lightPort = null;
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

  function recomputePorts() {
    const motors = [...ports.entries()]
      .filter(([, typeId]) => MOTOR_TYPE_IDS.has(typeId))
      .sort((a, b) => a[0] - b[0])
      .map(([portId]) => portId);
    if (leftPort === null || !ports.has(leftPort)) leftPort = motors[0] ?? null;
    if (rightPort === null || !ports.has(rightPort)) rightPort = motors[1] ?? motors[0] ?? null;

    const lights = [...ports.entries()].filter(([, t]) => LIGHT_TYPE_IDS.has(t)).map(([p]) => p);
    if (lightPort === null || !ports.has(lightPort)) lightPort = lights[0] ?? null;
  }

  function emitStatus(connected) {
    emit("status", {
      connected,
      name: device && device.name,
      ports: [...ports.entries()].map(([portId, typeId]) => ({
        portId, typeId, label: portLabel(portId),
        isMotor: MOTOR_TYPE_IDS.has(typeId),
        isLight: LIGHT_TYPE_IDS.has(typeId),
      })),
      leftPort, rightPort, lightPort,
    });
  }

  async function send(bytes) {
    if (!char) return;
    const payload = new Uint8Array(bytes.length + 1);
    payload[0] = bytes.length + 1; // LWP3 length byte includes itself
    payload.set(bytes, 1);
    await char.writeValue(payload);
  }

  function decodeValue(bytes) {
    if (bytes.length === 1) return bytes[0] > 127 ? bytes[0] - 256 : bytes[0];
    if (bytes.length === 2) { const v = bytes[0] | (bytes[1] << 8); return v > 32767 ? v - 65536 : v; }
    if (bytes.length === 4) {
      const v = (bytes[0] | (bytes[1] << 8) | (bytes[2] << 16) | (bytes[3] << 24));
      return v;
    }
    return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join(" ");
  }

  function onNotify(ev) {
    const bytes = new Uint8Array(ev.target.value.buffer);
    const msgType = bytes[2];
    if (msgType === 0x04) { // Hub Attached I/O
      const portId = bytes[3], event = bytes[4];
      if (event === 0x01) ports.set(portId, bytes[5] | (bytes[6] << 8)); // physical attach
      else if (event === 0x00) ports.delete(portId); // detach
      // event 0x02 (virtual/combined port) is ignored — we drive real ports individually
      recomputePorts();
      emitStatus(true);
    } else if (msgType === 0x01 && bytes[3] === 0x06 && bytes[4] === 0x06) {
      emit("battery", bytes[5]); // Hub Properties: Battery Voltage, Operation=Update
    } else if (msgType === 0x45) { // Port Value (Single)
      const portId = bytes[3];
      const value = decodeValue(bytes.slice(4));
      emit("portValue", { portId, label: portLabel(portId), value });
    }
  }

  function onDisconnected() {
    ports.clear();
    leftPort = rightPort = lightPort = null;
    emitStatus(false);
  }

  async function openConnection() {
    device.addEventListener("gattserverdisconnected", onDisconnected);
    server = await device.gatt.connect();
    const service = await server.getPrimaryService(SERVICE_UUID);
    char = await service.getCharacteristic(CHAR_UUID);
    await char.startNotifications();
    char.addEventListener("characteristicvaluechanged", onNotify);
    ports.clear();
    leftPort = rightPort = lightPort = null;
    emitStatus(true);
    await send([0x00, 0x01, 0x06, 0x02]); // subscribe to battery % updates
    try { localStorage.setItem(LAST_DEVICE_KEY, device.id); } catch (e) {}
  }

  // Opens the native chooser, listing every nearby LWP3 hub to pick from.
  async function scan() {
    device = await navigator.bluetooth.requestDevice({ filters: [{ services: [SERVICE_UUID] }] });
    await openConnection();
  }

  // Reconnects to the last-used hub without showing the chooser again
  // (relies on Chrome's persistent Bluetooth device permissions).
  async function reconnectLast() {
    if (!navigator.bluetooth.getDevices) throw new Error("Quick-reconnect isn't supported in this browser — use Scan instead.");
    const id = localStorage.getItem(LAST_DEVICE_KEY);
    if (!id) throw new Error("No previously connected hub found.");
    const known = await navigator.bluetooth.getDevices();
    const match = known.find((d) => d.id === id);
    if (!match) throw new Error("Previous hub is no longer authorized — use Scan instead.");
    device = match;
    await openConnection();
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
    await Promise.all([...ports.keys()].map((p) => (MOTOR_TYPE_IDS.has(ports.get(p)) ? setMotorPower(p, 0) : null)));
  }

  async function setHubLight(r, g, b) {
    if (lightPort === null) return;
    // WriteDirectModeData, Mode 1 (RGB) on the built-in Hub LED.
    await send([0x00, 0x81, lightPort, 0x11, 0x51, 0x01, r, g, b]);
  }

  async function enablePortNotifications(portId, mode) {
    // Port Input Format Setup (Single): subscribe to value updates for a port/mode.
    await send([0x00, 0x41, portId, mode ?? 0, 0x01, 0x00, 0x00, 0x00, 0x01]);
  }

  function setLeftPort(portId) { leftPort = portId; emitStatus(!!char); }
  function setRightPort(portId) { rightPort = portId; emitStatus(!!char); }
  function setLightPort(portId) { lightPort = portId; emitStatus(!!char); }

  return {
    get isSupported() { return !!navigator.bluetooth; },
    get canQuickReconnect() { return !!(navigator.bluetooth && navigator.bluetooth.getDevices && localStorage.getItem(LAST_DEVICE_KEY)); },
    on, scan, reconnectLast, disconnect,
    driveMotors, stop, setMotorPower, setHubLight, enablePortNotifications,
    setLeftPort, setRightPort, setLightPort,
  };
})();
