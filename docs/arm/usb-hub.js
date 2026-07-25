// USB-cable connection to the Technic Large Hub (88016) via the Web Serial
// API — Chrome/Edge on a computer only. The hub's stock SPIKE/MINDSTORMS
// firmware runs MicroPython and exposes a serial REPL over USB; we drop it
// into raw-REPL mode and send tiny Python snippets to spin the motors.
// Mirrors ArmHub's public surface (connect/disconnect/moveBase/moveShoulder/
// moveGripper/stopAll/nudge) so app.js can drive either backend.
//
// Why this exists: unlike the BOOST/Powered Up hubs, the 88016 hub's stock
// firmware does NOT speak the LWP3 Bluetooth protocol the ArmHub backend
// uses, so Bluetooth pairing from this app can fail on it. USB is the
// dependable path for this hub.

// Runs once at connect: defines _arm_run(port, speed) and _arm_deg(port,
// degrees, speed) that work on both hub firmware generations.
const USB_BOOTSTRAP = [
  'try:',
  '    import hub as _h',
  '    def _arm_run(p, s):',
  '        getattr(_h.port, p).motor.pwm(int(s))',
  '    def _arm_deg(p, d, s):',
  '        getattr(_h.port, p).motor.run_for_degrees(int(d), int(s))',
  'except ImportError:',
  '    import motor as _m',
  '    from hub import port as _p',
  '    def _arm_run(p, s):',
  '        s = int(s)',
  '        if s: _m.run(getattr(_p, p), s * 10)',
  '        else: _m.stop(getattr(_p, p))',
  '    def _arm_deg(p, d, s):',
  '        _m.run_for_degrees(getattr(_p, p), int(d), int(s) * 10)',
].join('\r\n');

class UsbArmHub {
  constructor({ onLog, onStatus } = {}) {
    this.onLog = onLog || (() => {});
    this.onStatus = onStatus || (() => {});
    this.port = null;
    this.writer = null;
    this.reader = null;
    this._stopTimer = null;
    this._encoder = new TextEncoder();
    this._decoder = new TextDecoder();
  }

  log(line) {
    this.onLog(line);
  }

  get isConnected() {
    return !!this.writer;
  }

  // Settings are shared with the Bluetooth backend — read live so Settings
  // changes apply immediately without re-connecting.
  _portLetter(which) {
    const idx = parseInt(localStorage.getItem({
      base: 'armBasePort', shoulder: 'armShoulderPort', gripper: 'armGripperPort',
    }[which]) ?? { base: 0, shoulder: 1, gripper: 2 }[which], 10);
    return portName(idx);
  }

  get speed() { return parseInt(localStorage.getItem('armSpeed') ?? '50', 10); }
  get moveSeconds() { return parseFloat(localStorage.getItem('armMoveSeconds') ?? '1'); }

  async connect() {
    if (!navigator.serial) {
      const msg = 'USB connection works in Chrome or Edge on a computer — not in phone browsers. Plug the hub into a computer and open this page there.';
      this.log(msg);
      this.onStatus('disconnected', null, msg);
      return;
    }
    try {
      this.onStatus('connecting');
      this.log('Opening the USB port picker...');
      this.port = await navigator.serial.requestPort();
      await this.port.open({ baudRate: 115200 });
      this.writer = this.port.writable.getWriter();
      this._readLoop();

      // Ctrl-C twice stops any running program, Ctrl-A enters raw REPL,
      // then the bootstrap defines our motor helpers and Ctrl-D runs it.
      await this._writeRaw('\x03\x03');
      await new Promise((r) => setTimeout(r, 300));
      await this._writeRaw('\x01');
      await new Promise((r) => setTimeout(r, 200));
      await this._writeRaw(USB_BOOTSTRAP + '\x04');
      this.onStatus('connected', 'USB hub');
      this.log('Connected over USB.');
    } catch (err) {
      this._cleanup();
      this.onStatus('disconnected', null, err.message);
      this.log('USB connect failed: ' + err.message);
    }
  }

  async disconnect() {
    try {
      if (this.writer) {
        await this._exec(this._allStopCode());
        await this._writeRaw('\x02'); // back to the friendly REPL
      }
    } catch (err) { /* port may already be gone */ }
    this._cleanup();
    this.onStatus('disconnected');
    this.log('USB disconnected.');
  }

  _cleanup() {
    clearTimeout(this._stopTimer);
    try { if (this.reader) this.reader.cancel(); } catch (e) { /* noop */ }
    try { if (this.writer) this.writer.releaseLock(); } catch (e) { /* noop */ }
    this.writer = null;
    this.reader = null;
    try { if (this.port) this.port.close(); } catch (e) { /* noop */ }
    this.port = null;
  }

  async _readLoop() {
    try {
      while (this.port && this.port.readable) {
        this.reader = this.port.readable.getReader();
        try {
          for (;;) {
            const { value, done } = await this.reader.read();
            if (done) break;
            const text = this._decoder.decode(value).trim();
            if (text) this.log('<- ' + text.slice(0, 120));
          }
        } finally {
          this.reader.releaseLock();
        }
      }
    } catch (err) {
      // Cable pulled mid-read — treat as a disconnect.
      if (this.writer) {
        this._cleanup();
        this.onStatus('disconnected', null, 'USB connection lost: ' + err.message);
        this.log('USB connection lost: ' + err.message);
      }
    }
  }

  async _writeRaw(text) {
    await this.writer.write(this._encoder.encode(text));
  }

  /** Runs one Python snippet in the hub's raw REPL. */
  async _exec(code) {
    if (!this.writer) {
      this.log("Not connected — can't send.");
      return;
    }
    try {
      await this._writeRaw(code + '\x04');
      this.log('-> ' + code.replace(/\r\n/g, ' ; '));
    } catch (err) {
      this.log('USB write failed: ' + err.message);
    }
  }

  _allStopCode() {
    const ports = ['base', 'shoulder', 'gripper'].map((w) => this._portLetter(w));
    return ports.map((p) => `_arm_run('${p}', 0)`).join('\r\n');
  }

  _jog(which, sign, label) {
    clearTimeout(this._stopTimer);
    this._exec(`_arm_run('${this._portLetter(which)}', ${this.speed * sign})`);
    this._stopTimer = setTimeout(() => this.stopAll(), this.moveSeconds * 1000);
    this.log(label);
  }

  moveBase(direction) {
    this._jog('base', direction === 'left' ? -1 : 1, 'Base -> ' + direction);
  }

  moveShoulder(direction) {
    this._jog('shoulder', direction === 'up' ? 1 : -1, 'Shoulder -> ' + direction);
  }

  moveGripper(action) {
    this._jog('gripper', action === 'open' ? -1 : 1, 'Gripper -> ' + action);
  }

  stopAll() {
    clearTimeout(this._stopTimer);
    this._exec(this._allStopCode());
    this.log('Stopping.');
  }

  /** Nudge by port number (same PORT indices the Bluetooth backend uses). */
  nudge(portIndex) {
    this._exec(`_arm_deg('${portName(portIndex)}', 30, 30)`);
    this.log('Nudged port ' + portName(portIndex) + '.');
  }
}
