// Real code/scripting for the rover: run user-written JavaScript against a
// small async robot API (forward/turnLeft/clawClose/wait/…). This is the
// in-browser equivalent of Pybricks — the user gets loops, variables and
// conditionals for free because it's real JS. Works on iPhone (typing +
// Bluetooth, no microphone).
//
// The code is the user's own, running in their own browser, so there's no
// remote eval and no sandbox beyond try/catch. A cancellation token lets the
// Stop button halt a running script promptly.

class StopError extends Error {}

// AsyncFunction constructor (not a global) so user code can use `await`.
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

class RoverScript {
  constructor({ hub, onLog, onRunning } = {}) {
    this.hub = hub;
    this.onLog = onLog || (() => {});
    this.onRunning = onRunning || (() => {});
    this._token = null;
  }

  get running() {
    return !!this._token && !this._token.cancelled;
  }

  stop() {
    if (this._token) this._token.cancelled = true;
    try { this.hub.stopAll(); } catch (e) { /* noop */ }
  }

  async run(code) {
    if (this.running) {
      this.onLog('A script is already running — press Stop first.');
      return;
    }
    if (!this.hub || !this.hub.isConnected) {
      this.onLog("The hub isn't connected. Go to the Connect tab first.");
      return;
    }
    const token = { cancelled: false };
    this._token = token;
    this.onRunning(true);
    this.onLog('▶ Running…');

    const api = this._makeApi(token);
    try {
      const fn = new AsyncFunction(...Object.keys(api), code);
      await fn(...Object.values(api));
      if (!token.cancelled) this.onLog('✓ Done.');
    } catch (err) {
      if (err instanceof StopError) {
        this.onLog('■ Stopped.');
      } else {
        this.onLog('✗ Error: ' + (err && err.message ? err.message : String(err)));
      }
    } finally {
      try { this.hub.stopAll(); } catch (e) { /* noop */ }
      this._token = null;
      this.onRunning(false);
    }
  }

  _makeApi(token) {
    const check = () => { if (token.cancelled) throw new StopError(); };
    const hub = this.hub;
    const log = (...args) => this.onLog(args.map((a) => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' '));

    // Cancellable sleep — wakes in slices so Stop responds quickly.
    const wait = async (sec) => {
      const ms = Math.max(0, (Number(sec) || 0) * 1000);
      const end = performance.now() + ms;
      while (performance.now() < end) {
        check();
        await new Promise((r) => setTimeout(r, Math.min(100, end - performance.now())));
      }
      check();
    };

    const moveFor = async (fn, sec, fallback) => {
      check();
      fn();
      await wait(sec == null ? fallback : sec);
      hub.stopAll();
    };

    const COLORS = {
      off: 0, black: 0, pink: 1, magenta: 1, purple: 2, violet: 2,
      blue: 3, lightblue: 4, cyan: 5, teal: 5, green: 6, lime: 6,
      yellow: 7, orange: 8, red: 9, white: 10,
    };

    return {
      forward: (sec) => moveFor(() => hub.driveDir('forward'), sec, hub.driveSeconds),
      backward: (sec) => moveFor(() => hub.driveDir('backward'), sec, hub.driveSeconds),
      left: (sec) => moveFor(() => hub.turnDir('left'), sec, hub.turnSeconds),
      right: (sec) => moveFor(() => hub.turnDir('right'), sec, hub.turnSeconds),
      turnLeft: (sec) => moveFor(() => hub.turnDir('left'), sec, hub.turnSeconds),
      turnRight: (sec) => moveFor(() => hub.turnDir('right'), sec, hub.turnSeconds),
      // Independent-wheel driving for a duration — curves, spins, anything.
      arc: async (leftPercent, rightPercent, sec) => {
        check();
        hub.motors(leftPercent, rightPercent);
        await wait(sec == null ? hub.driveSeconds : sec);
        hub.stopAll();
      },
      // Set both motors and keep going until stop()/next command.
      setMotors: (leftPercent, rightPercent) => { check(); hub.motors(leftPercent, rightPercent); },
      setSpeed: (percent) => { check(); hub.driveSpeed = Math.max(0, Math.min(100, Math.round(Number(percent) || 0))); },
      stop: () => { check(); hub.stopAll(); },
      headLeft: () => { check(); hub.turnHead('left'); },
      headRight: () => { check(); hub.turnHead('right'); },
      headCenter: () => { check(); hub.turnHead('center'); },
      head: (degrees) => { check(); hub.headTo(degrees); },
      clawOpen: () => { check(); hub.claw('open'); },
      clawClose: () => { check(); hub.claw('close'); },
      light: (color) => {
        check();
        const idx = typeof color === 'number' ? color : (COLORS[String(color).toLowerCase()] ?? 10);
        hub.setLight(idx);
      },
      random: (min, max) => {
        if (max == null) { max = min == null ? 1 : min; min = 0; }
        return Math.random() * (Number(max) - Number(min)) + Number(min);
      },
      repeat: async (n, fn) => {
        for (let i = 0; i < n; i++) { check(); await fn(i); }
      },
      wait,
      log,
      print: log,
    };
  }
}
