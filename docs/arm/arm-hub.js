// Owns the Web Bluetooth connection to the LEGO Powered Up Technic Large
// Hub (88016) and exposes plain high-level methods for the arm's three
// motors (base rotation + shoulder lift + gripper). Adapted from
// docs/rover/rover-hub.js — same connection/reconnect/notify plumbing,
// different high-level API (moveBase/moveShoulder/moveGripper instead of
// drive/turn/claw).
//
// Web Bluetooth does not work in Safari on iPhone — use the Bluefy browser
// app instead. See README.md.
class ArmHub {
  constructor({ onLog, onStatus } = {}) {
    this.onLog = onLog || (() => {});
    this.onStatus = onStatus || (() => {});
    this.device = null;
    this.characteristic = null;
    this._stopTimer = null;
    this._userDisconnected = false;
    this._reconnecting = false;

    this.basePort = this._loadInt('armBasePort', PORT.A);
    this.shoulderPort = this._loadInt('armShoulderPort', PORT.B);
    this.gripperPort = this._loadInt('armGripperPort', PORT.C);
    this.speed = this._loadInt('armSpeed', 50);
    this.moveSeconds = this._loadFloat('armMoveSeconds', 1.0);
  }

  log(line) {
    this.onLog(line);
  }

  get isConnected() {
    return !!this.characteristic;
  }

  async connect() {
    if (!navigator.bluetooth) {
      const msg = "Web Bluetooth isn't available in this browser. On iPhone, use the Bluefy app instead of Safari.";
      this.log(msg);
      this.onStatus('disconnected', null, msg);
      return;
    }
    try {
      this._userDisconnected = false;
      this.onStatus('connecting');
      this.log('Opening the Bluetooth device picker...');
      // acceptAllDevices instead of a services filter: some hub
      // firmware/BLE stack combinations don't advertise the full 128-bit
      // service UUID in every packet, which can make filtered
      // requestDevice() calls silently show an empty picker. Showing every
      // nearby device is less tidy but far more reliable — look for "LEGO"
      // or "Technic Hub" in the list.
      this.device = await navigator.bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: [HUB_SERVICE_UUID],
      });
      this.device.addEventListener('gattserverdisconnected', () => this._onDisconnected());
      this.log(`Picked "${this.device.name || 'unnamed device'}". Connecting to it...`);
      await this._attachServer();
      this.log(`Connected to ${this.device.name || 'LEGO hub'}.`);
    } catch (err) {
      this.onStatus('disconnected', null, err.message);
      this.log('Connect failed: ' + err.message);
    }
  }

  /** Connect GATT and wire up the characteristic. Shared by first connect
   * and auto-reconnect. Assumes this.device is already set. */
  async _attachServer() {
    const server = await this.device.gatt.connect();
    const service = await server.getPrimaryService(HUB_SERVICE_UUID);
    this.characteristic = await service.getCharacteristic(HUB_CHARACTERISTIC_UUID);
    await this.characteristic.startNotifications();
    this.characteristic.addEventListener('characteristicvaluechanged', (e) => this._onNotify(e.target.value));
    this.onStatus('connected', this.device.name || 'LEGO Hub');
  }

  _onDisconnected() {
    this.characteristic = null;
    this.onStatus('disconnected');
    this.log('Disconnected.');
    if (!this._userDisconnected) {
      this._reconnect();
    }
  }

  /** Try to silently reconnect to the same hub (no device picker) after an
   * unexpected drop. iOS may require a fresh user gesture, in which case we
   * give up gracefully and tell the user to tap Connect. */
  async _reconnect() {
    if (this._reconnecting || !this.device) return;
    this._reconnecting = true;
    for (let attempt = 1; attempt <= 3; attempt++) {
      if (this._userDisconnected) break;
      this.onStatus('connecting');
      this.log(`Reconnecting to the hub… (attempt ${attempt} of 3)`);
      try {
        await this._attachServer();
        this.log('Reconnected.');
        this._reconnecting = false;
        return;
      } catch (err) {
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
    this._reconnecting = false;
    this.onStatus('disconnected');
    this.log("Couldn't reconnect automatically — tap Connect to reconnect.");
  }

  disconnect() {
    this._userDisconnected = true;
    if (this.device && this.device.gatt.connected) {
      this.device.gatt.disconnect();
    }
  }

  /** Rotate the base left/right for `moveSeconds`, then auto-stop. */
  moveBase(direction) {
    clearTimeout(this._stopTimer);
    const sign = direction === 'left' ? -1 : 1;
    this._sendPower(this.basePort, this.speed * sign);
    this._scheduleAutoStop();
    this.log('Base -> ' + direction);
  }

  /** Lift the shoulder up/down for `moveSeconds`, then auto-stop. */
  moveShoulder(direction) {
    clearTimeout(this._stopTimer);
    const sign = direction === 'up' ? 1 : -1;
    this._sendPower(this.shoulderPort, this.speed * sign);
    this._scheduleAutoStop();
    this.log('Shoulder -> ' + direction);
  }

  /** Open/close the gripper for `moveSeconds`, then auto-stop. Power-based
   * jog like the other axes, so it works with any Powered Up motor and any
   * gripper mechanism — closing stalls gently against the object, and the
   * auto-stop keeps a stall from running forever. */
  moveGripper(action) {
    clearTimeout(this._stopTimer);
    const sign = action === 'open' ? -1 : 1;
    this._sendPower(this.gripperPort, this.speed * sign);
    this._scheduleAutoStop();
    this.log('Gripper -> ' + action);
  }

  stopAll() {
    clearTimeout(this._stopTimer);
    this._sendPower(this.basePort, 0);
    this._sendPower(this.shoulderPort, 0);
    this._sendPower(this.gripperPort, 0);
    this.log('Stopping.');
  }

  /** Nudges a port a small amount so the user can see which physical motor
   * (base or shoulder) it corresponds to, before wiring is finalized. */
  nudge(port) {
    this._write(gotoAbsolutePosition(port, 30, 30, 50, END_STATE.HOLD));
    this.log('Nudged port ' + portName(port) + '.');
  }

  setBasePort(port) { this.basePort = port; localStorage.setItem('armBasePort', String(port)); }
  setShoulderPort(port) { this.shoulderPort = port; localStorage.setItem('armShoulderPort', String(port)); }
  setGripperPort(port) { this.gripperPort = port; localStorage.setItem('armGripperPort', String(port)); }
  setSpeed(v) { this.speed = v; localStorage.setItem('armSpeed', String(v)); }
  setMoveSeconds(v) { this.moveSeconds = v; localStorage.setItem('armMoveSeconds', String(v)); }

  // MARK: internals

  _loadInt(key, fallback) {
    const v = localStorage.getItem(key);
    return v === null ? fallback : parseInt(v, 10);
  }

  _loadFloat(key, fallback) {
    const v = localStorage.getItem(key);
    return v === null ? fallback : parseFloat(v);
  }

  _scheduleAutoStop() {
    clearTimeout(this._stopTimer);
    this._stopTimer = setTimeout(() => this.stopAll(), this.moveSeconds * 1000);
  }

  _sendPower(port, power) {
    this._write(writeDirectModeDataPower(port, power));
  }

  async _write(bytes) {
    if (!this.characteristic) {
      this.log("Not connected — can't send.");
      return;
    }
    try {
      await this.characteristic.writeValueWithoutResponse(bytes);
      this.log('-> ' + toHex(bytes));
    } catch (err) {
      this.log('Write failed: ' + err.message);
    }
  }

  _onNotify(dataView) {
    const bytes = new Uint8Array(dataView.buffer);
    this.log('<- ' + toHex(bytes));
    const event = parseHubAttachedIO(bytes);
    if (event) {
      if (event.attached) {
        const typeHex = (event.ioTypeID ?? 0).toString(16).padStart(4, '0');
        this.log(`Port ${portName(event.port)}: attached (IO type 0x${typeHex})`);
      } else {
        this.log(`Port ${portName(event.port)}: detached`);
      }
    }
  }
}
