// UI wiring: tab switching, button -> RoverHub calls, console command
// parsing, settings <-> RoverHub sync, and the log view.

/** A tiny command language for the console box — typed shorthand for the
 * same actions the Controller tab's buttons trigger, plus a "raw" escape
 * hatch for sending hand-crafted LWP3 bytes while debugging. */
function runConsoleCommand(raw, hub) {
  const text = raw.trim().toLowerCase();
  if (!text) return;
  const parts = text.split(/\s+/);

  switch (parts[0]) {
    case 'forward':
    case 'fwd':
      hub.drive('forward');
      break;
    case 'backward':
    case 'back':
      hub.drive('backward');
      break;
    case 'left':
      hub.turn('left');
      break;
    case 'right':
      hub.turn('right');
      break;
    case 'stop':
      hub.stopAll();
      break;
    case 'head': {
      const dir = parts[1] || 'center';
      hub.turnHead(dir === 'left' ? 'left' : dir === 'right' ? 'right' : 'center');
      break;
    }
    case 'claw':
      hub.claw(parts[1] === 'close' ? 'close' : 'open');
      break;
    case 'scan':
      hub.connect();
      break;
    case 'raw':
      hub.sendRaw(parts.slice(1).join(''));
      break;
    default:
      hub.log(
        `Unknown command: ${text} (try: forward, backward, left, right, stop, ` +
        'head left/right/center, claw open/close, scan, raw <hex>)'
      );
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const statusEl = document.getElementById('status');
  const logEl = document.getElementById('log');

  const hub = new RoverHub({
    onLog: (line) => {
      const div = document.createElement('div');
      div.textContent = line;
      logEl.appendChild(div);
      while (logEl.childElementCount > 300) logEl.removeChild(logEl.firstChild);
      logEl.scrollTop = logEl.scrollHeight;
    },
    onStatus: (state, name) => {
      const labels = {
        disconnected: 'Not connected',
        connecting: 'Connecting…',
        connected: `Connected: ${name || ''}`,
      };
      statusEl.textContent = labels[state] || state;
      statusEl.className = 'status ' + state;
      document.getElementById('disconnectBtn').hidden = state !== 'connected';
    },
  });

  // --- Tabs ---
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
  });

  // --- Connect tab ---
  document.getElementById('connectBtn').addEventListener('click', () => hub.connect());
  document.getElementById('disconnectBtn').addEventListener('click', () => hub.disconnect());

  // --- Controller tab ---
  document.getElementById('fwdBtn').addEventListener('click', () => hub.drive('forward'));
  document.getElementById('backBtn').addEventListener('click', () => hub.drive('backward'));
  document.getElementById('leftBtn').addEventListener('click', () => hub.turn('left'));
  document.getElementById('rightBtn').addEventListener('click', () => hub.turn('right'));
  document.getElementById('stopBtn').addEventListener('click', () => hub.stopAll());
  document.getElementById('headLeftBtn').addEventListener('click', () => hub.turnHead('left'));
  document.getElementById('headCenterBtn').addEventListener('click', () => hub.turnHead('center'));
  document.getElementById('headRightBtn').addEventListener('click', () => hub.turnHead('right'));
  document.getElementById('clawOpenBtn').addEventListener('click', () => hub.claw('open'));
  document.getElementById('clawCloseBtn').addEventListener('click', () => hub.claw('close'));
  document.getElementById('nudgeCBtn').addEventListener('click', () => hub.nudge(PORT.C));
  document.getElementById('nudgeDBtn').addEventListener('click', () => hub.nudge(PORT.D));

  // --- Console tab ---
  const consoleForm = document.getElementById('consoleForm');
  const consoleInput = document.getElementById('consoleInput');
  consoleForm.addEventListener('submit', (e) => {
    e.preventDefault();
    runConsoleCommand(consoleInput.value, hub);
    consoleInput.value = '';
  });

  // --- Settings tab ---
  const clawPortSel = document.getElementById('clawPortSel');
  const headPortSel = document.getElementById('headPortSel');
  const portWarning = document.getElementById('portWarning');
  const speedInput = document.getElementById('speedInput');
  const driveSecInput = document.getElementById('driveSecInput');
  const turnSecInput = document.getElementById('turnSecInput');

  function refreshPortWarning() {
    portWarning.hidden = clawPortSel.value !== headPortSel.value;
  }

  clawPortSel.value = String(hub.clawPort);
  headPortSel.value = String(hub.headPort);
  speedInput.value = String(hub.driveSpeed);
  driveSecInput.value = String(hub.driveSeconds);
  turnSecInput.value = String(hub.turnSeconds);
  refreshPortWarning();

  clawPortSel.addEventListener('change', () => {
    hub.setClawPort(parseInt(clawPortSel.value, 10));
    refreshPortWarning();
  });
  headPortSel.addEventListener('change', () => {
    hub.setHeadPort(parseInt(headPortSel.value, 10));
    refreshPortWarning();
  });
  speedInput.addEventListener('change', () => hub.setDriveSpeed(parseInt(speedInput.value, 10)));
  driveSecInput.addEventListener('change', () => hub.setDriveSeconds(parseFloat(driveSecInput.value)));
  turnSecInput.addEventListener('change', () => hub.setTurnSeconds(parseFloat(turnSecInput.value)));

  if (!navigator.bluetooth) {
    hub.log("Heads up: this browser doesn't support Web Bluetooth. On iPhone, install the free/cheap 'Bluefy' app from the App Store and open this page there instead of Safari.");
  }
});
