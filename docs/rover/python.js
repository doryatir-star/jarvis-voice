// Write real Python to control the rover — an original, in-browser
// implementation (no firmware flash, no copied code). Python runs via Brython
// (open-source, brython.js) and calls the same rover API the JS Code tab uses,
// so the stock-firmware rover keeps working exactly as now.
//
// EXPERIMENTAL: verified in desktop Chrome; whether Brython runs in Bluefy on
// an older iPhone is the open question. The JS "Code" tab is the reliable path.

class RoverPython {
  constructor({ hub, onLog, onRunning } = {}) {
    this.hub = hub;
    this.onLog = onLog || (() => {});
    this.onRunning = onRunning || (() => {});
    this._token = null;
    this._brythonReady = false;
  }

  get running() {
    return !!this._token && !this._token.cancelled;
  }

  stop() {
    if (this._token) this._token.cancelled = true;
    try { this.hub.stopAll(); } catch (e) { /* noop */ }
  }

  _ensureBrython() {
    return new Promise((resolve, reject) => {
      if (this._brythonReady) { resolve(); return; }
      const finish = () => {
        // brython.js is loaded after DOMContentLoaded, so its normal init
        // hooks don't fire. Prime the runtime with an empty pass so the first
        // real program actually executes (an un-primed first brython() call
        // silently does nothing).
        try { window.brython({ debug: 0 }); } catch (e) { /* priming */ }
        this._brythonReady = true;
        resolve();
      };
      if (window.brython) { finish(); return; }
      const s = document.createElement('script');
      s.src = 'brython.js';
      s.onload = finish;
      s.onerror = () => reject(new Error('Could not load the Python engine (brython.js).'));
      document.head.appendChild(s);
    });
  }

  async run(code) {
    if (this.running) { this.onLog('A program is already running — press Stop first.'); return; }
    if (!this.hub || !this.hub.isConnected) {
      this.onLog("The hub isn't connected. Go to the Connect tab first.");
      return;
    }
    const token = { cancelled: false };
    this._token = token;
    this.onRunning(true);
    this.onLog('▶ Running Python…');

    try {
      await this._ensureBrython();
    } catch (e) {
      this.onLog('✗ ' + e.message);
      this._token = null;
      this.onRunning(false);
      return;
    }

    // Expose the shared rover API to Python via window.__rover.
    const api = makeRoverApi(this.hub, token, this.onLog);
    window.__rover = api;

    // Completion / error callbacks Python calls back into.
    window.__roverDone = () => {
      if (!token.cancelled) this.onLog('✓ Done.');
      this._finish(token);
    };
    window.__roverErr = (msg) => {
      const m = String(msg || '');
      if (/ROVER_STOP/.test(m) || token.cancelled) this.onLog('■ Stopped.');
      else this.onLog('✗ Error: ' + m);
      this._finish(token);
    };

    // Indent the user's code into an async main(). Bind Pythonic names to the
    // JS rover API; `print` routes to our output.
    const indented = code.split('\n').map((l) => '        ' + l).join('\n');
    const pySrc = [
      'from browser import window, aio',
      '_r = window.__rover',
      'forward = _r.forward',
      'backward = _r.backward',
      'left = _r.left',
      'right = _r.right',
      'arc = _r.arc',
      'set_motors = _r.setMotors',
      'set_speed = _r.setSpeed',
      'head = _r.head',
      'head_left = _r.headLeft',
      'head_right = _r.headRight',
      'head_center = _r.headCenter',
      'claw_open = _r.clawOpen',
      'claw_close = _r.clawClose',
      'light = _r.light',
      'stop = _r.stop',
      'wait = _r.wait',
      'rand = _r.random',
      'log = _r.log',
      'print = _r.log',
      'async def __main__():',
      '    try:',
      indented || '        pass',
      '    except Exception as e:',
      '        window.__roverErr(repr(e))',
      '        return',
      '    window.__roverDone()',
      'aio.run(__main__())',
    ].join('\n');

    try {
      // Remove any previous program script so brython() only runs the new one.
      if (this._scriptEl && this._scriptEl.parentNode) this._scriptEl.parentNode.removeChild(this._scriptEl);
      const s = document.createElement('script');
      s.type = 'text/python';
      s.textContent = pySrc;
      document.body.appendChild(s);
      this._scriptEl = s;
      window.brython({ debug: 0 });
    } catch (e) {
      // Syntax errors during Brython compilation land here.
      this.onLog('✗ Error: ' + (e && e.message ? e.message : String(e)));
      this._finish(token);
    }
  }

  _finish(token) {
    if (this._token !== token) return;
    try { this.hub.stopAll(); } catch (e) { /* noop */ }
    this._token = null;
    this.onRunning(false);
  }
}
