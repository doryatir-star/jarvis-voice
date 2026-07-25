// UI wiring: tab switching, parts-checklist persistence, button -> ArmHub
// calls, and settings <-> ArmHub sync. Adapted from docs/rover/app.js, with
// the voice/code/python/console tabs dropped — this app is a build guide
// plus a minimal wiring-test controller, not a full scripting environment.

document.addEventListener('DOMContentLoaded', () => {
  const statusEl = document.getElementById('status');
  const logEl = document.getElementById('log');

  const hub = new ArmHub({
    onLog: (line) => {
      const div = document.createElement('div');
      div.textContent = line;
      logEl.appendChild(div);
      while (logEl.childElementCount > 300) logEl.removeChild(logEl.firstChild);
      logEl.scrollTop = logEl.scrollHeight;
    },
    onStatus: (state, name, errorMessage) => {
      const labels = {
        disconnected: 'Not connected',
        connecting: 'Connecting…',
        connected: `Connected: ${name || ''}`,
      };
      statusEl.textContent = labels[state] || state;
      statusEl.className = 'status ' + state;
      document.getElementById('disconnectBtn').hidden = state !== 'connected';

      const errorEl = document.getElementById('connectError');
      if (errorMessage) {
        errorEl.textContent = errorMessage;
        errorEl.hidden = false;
        window.alert('Connect failed:\n\n' + errorMessage);
      } else if (state === 'connecting') {
        errorEl.hidden = true;
      }
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

  // --- Guide tab: parts checklist persistence ---
  document.querySelectorAll('#partsChecklist input[type="checkbox"]').forEach((box) => {
    const key = 'armPart_' + box.dataset.key;
    box.checked = localStorage.getItem(key) === '1';
    box.addEventListener('change', () => {
      localStorage.setItem(key, box.checked ? '1' : '0');
    });
  });

  // --- Test tab: connect ---
  document.getElementById('connectBtn').addEventListener('click', () => hub.connect());
  document.getElementById('disconnectBtn').addEventListener('click', () => hub.disconnect());

  // --- Test tab: base/shoulder/nudge ---
  document.getElementById('baseLeftBtn').addEventListener('click', () => hub.moveBase('left'));
  document.getElementById('baseRightBtn').addEventListener('click', () => hub.moveBase('right'));
  document.getElementById('baseStopBtn').addEventListener('click', () => hub.stopAll());
  document.getElementById('shoulderUpBtn').addEventListener('click', () => hub.moveShoulder('up'));
  document.getElementById('shoulderDownBtn').addEventListener('click', () => hub.moveShoulder('down'));
  document.getElementById('shoulderStopBtn').addEventListener('click', () => hub.stopAll());
  document.getElementById('gripperOpenBtn').addEventListener('click', () => hub.moveGripper('open'));
  document.getElementById('gripperCloseBtn').addEventListener('click', () => hub.moveGripper('close'));
  document.getElementById('gripperStopBtn').addEventListener('click', () => hub.stopAll());
  document.getElementById('nudgeABtn').addEventListener('click', () => hub.nudge(PORT.A));
  document.getElementById('nudgeBBtn').addEventListener('click', () => hub.nudge(PORT.B));
  document.getElementById('nudgeCBtn').addEventListener('click', () => hub.nudge(PORT.C));

  // --- Settings tab ---
  const basePortSel = document.getElementById('basePortSel');
  const shoulderPortSel = document.getElementById('shoulderPortSel');
  const gripperPortSel = document.getElementById('gripperPortSel');
  const portWarning = document.getElementById('portWarning');
  const speedInput = document.getElementById('speedInput');
  const moveSecInput = document.getElementById('moveSecInput');

  function refreshPortWarning() {
    const ports = [basePortSel.value, shoulderPortSel.value, gripperPortSel.value];
    portWarning.hidden = new Set(ports).size === ports.length;
  }

  basePortSel.value = String(hub.basePort);
  shoulderPortSel.value = String(hub.shoulderPort);
  gripperPortSel.value = String(hub.gripperPort);
  speedInput.value = String(hub.speed);
  moveSecInput.value = String(hub.moveSeconds);
  refreshPortWarning();

  basePortSel.addEventListener('change', () => {
    hub.setBasePort(parseInt(basePortSel.value, 10));
    refreshPortWarning();
  });
  shoulderPortSel.addEventListener('change', () => {
    hub.setShoulderPort(parseInt(shoulderPortSel.value, 10));
    refreshPortWarning();
  });
  gripperPortSel.addEventListener('change', () => {
    hub.setGripperPort(parseInt(gripperPortSel.value, 10));
    refreshPortWarning();
  });
  speedInput.addEventListener('change', () => hub.setSpeed(parseInt(speedInput.value, 10)));
  moveSecInput.addEventListener('change', () => hub.setMoveSeconds(parseFloat(moveSecInput.value)));

  if (!navigator.bluetooth) {
    hub.log("Heads up: this browser doesn't support Web Bluetooth. On iPhone, install the free/cheap 'Bluefy' app from the App Store and open this page there instead of Safari.");
  }
});
