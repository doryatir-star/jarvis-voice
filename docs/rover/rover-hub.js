// Owns the Web Bluetooth connection to the LEGO Move Hub and exposes plain
// high-level methods (drive/turn/stopAll/turnHead/claw) — mirrors the shape
// of the Windows app's LegoHub class and the iOS app's HubManager, adapted
// to the browser's promise-based Web Bluetooth API.
//
// Web Bluetooth does not work in Safari on iPhone — use the Bluefy browser
// app instead. See README.md.
class RoverHub {
  constructor({ onLog, onStatus } = {}) {
    this.onLog = onLog || (() => {});
    this.onStatus = onStatus || (() => {});
    this.device = null;
    this.characteristic = null;
    this._stopTimer = null;
    this._userDisconnected = false;
    this._reconnecting = false;

    this.clawPort = this._loadInt('clawPort', PORT.D);
    this.headPort = this._loadInt('headPort', PORT.C);
    this.driveSpeed = this._loadInt('driveSpeed', 60);
    this.driveSeconds = this._loadFloat('driveSeconds', 1.5);
    this.turnSeconds = this._loadFloat('turnSeconds', 0.8);
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
      // Using acceptAllDevices instead of a services filter: some LEGO hub
      // firmware/BLE stack combinations don't put the full 128-bit service
      // UUID in every advertisement packet, which can make filtered
      // requestDevice() calls silently show an empty picker (or none at
      // all) instead of a clear error. Showing every nearby device is less
      // tidy but far more reliable — look for "LEGO" or "Move Hub" in the
      // list.
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

  drive(direction) {
    const sign = direction === 'forward' ? 1 : -1;
    this._sendPower(PORT.A, this.driveSpeed * sign);
    this._sendPower(PORT.B, this.driveSpeed * sign);
    this._scheduleAutoStop(this.driveSeconds);
    this.log(direction === 'forward' ? 'Moving forward.' : 'Moving backward.');
  }

  turn(direction) {
    const left = direction === 'left' ? -this.driveSpeed : this.driveSpeed;
    const right = direction === 'left' ? this.driveSpeed : -this.driveSpeed;
    this._sendPower(PORT.A, left);
    this._sendPower(PORT.B, right);
    this._scheduleAutoStop(this.turnSeconds);
    this.log(direction === 'left' ? 'Turning left.' : 'Turning right.');
  }

  stopAll() {
    clearTimeout(this._stopTimer);
    this._sendPower(PORT.A, 0);
    this._sendPower(PORT.B, 0);
    this.log('Stopping.');
  }

  turnHead(direction) {
    const angle = direction === 'left' ? -90 : direction === 'right' ? 90 : 0;
    this._write(gotoAbsolutePosition(this.headPort, angle, 40, 60, END_STATE.HOLD));
    this.log('Head -> ' + direction);
  }

  claw(action) {
    const angle = action === 'open' ? -60 : 60;
    this._write(gotoAbsolutePosition(this.clawPort, angle, 40, 60, END_STATE.HOLD));
    this.log('Claw -> ' + action);
  }

  /** Nudges an external port a small amount so the user can see which
   * physical motor (claw or head) it corresponds to. */
  nudge(port) {
    this._write(gotoAbsolutePosition(port, 30, 30, 50, END_STATE.HOLD));
    this.log('Nudged port ' + portName(port) + '.');
  }

  sendRaw(hex) {
    const bytes = hexToBytes(hex);
    if (!bytes) {
      this.log('Bad hex: ' + hex);
      return;
    }
    this._write(bytes);
  }

  setClawPort(port) { this.clawPort = port; localStorage.setItem('clawPort', String(port)); }
  setHeadPort(port) { this.headPort = port; localStorage.setItem('headPort', String(port)); }
  setDriveSpeed(v) { this.driveSpeed = v; localStorage.setItem('driveSpeed', String(v)); }
  setDriveSeconds(v) { this.driveSeconds = v; localStorage.setItem('driveSeconds', String(v)); }
  setTurnSeconds(v) { this.turnSeconds = v; localStorage.setItem('turnSeconds', String(v)); }

  // MARK: internals

  _loadInt(key, fallback) {
    const v = localStorage.getItem(key);
    return v === null ? fallback : parseInt(v, 10);
  }

  _loadFloat(key, fallback) {
    const v = localStorage.getItem(key);
    return v === null ? fallback : parseFloat(v);
  }

  _scheduleAutoStop(seconds) {
    clearTimeout(this._stopTimer);
    this._stopTimer = setTimeout(() => this.stopAll(), seconds * 1000);
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
