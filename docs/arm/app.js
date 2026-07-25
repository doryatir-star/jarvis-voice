// UI wiring: tab switching, the LEGO-instructions-style step pager, button
// -> ArmHub calls, and settings <-> ArmHub sync. Adapted from
// docs/rover/app.js, with the voice/code/python/console tabs dropped — this
// app is a build guide plus a minimal wiring-test controller, not a full
// scripting environment.

// --- Step illustrations -----------------------------------------------------
// One SVG scene per step, LEGO-manual style: parts already built are dimmed,
// the pieces added this step are full-color. Everything is drawn from the
// same side view so the arm visibly grows page by page. All drawing is
// inline SVG — no image files, so it loads instantly and works offline.

const ARM_SVG = (() => {
  // state: 'dim' fades a part that was built in an earlier step.
  const g = (state, inner) => `<g${state === 'dim' ? ' opacity="0.28"' : ''}>${inner}</g>`;

  const PLATE =
    '<rect x="70" y="252" width="260" height="16" rx="3" fill="#3a3a3e"/>' +
    [...Array(9)].map((_, i) => `<circle cx="${92 + i * 27}" cy="252" r="4" fill="#4a4a4f"/>`).join('');

  const HUB =
    '<rect x="18" y="196" width="66" height="62" rx="8" fill="#f2f2f2"/>' +
    '<circle cx="51" cy="230" r="9" fill="#dcdcdc" stroke="#b5b5b5" stroke-width="2"/>' +
    '<rect x="28" y="204" width="12" height="6" rx="2" fill="#cfcfcf"/>' +
    '<rect x="62" y="204" width="12" height="6" rx="2" fill="#cfcfcf"/>';

  const MOTOR1 =
    '<rect x="185" y="210" width="44" height="42" rx="6" fill="#9a9aa0"/>' +
    '<rect x="199" y="200" width="16" height="12" rx="2" fill="#6e6e72"/>' +
    '<circle cx="207" cy="231" r="6" fill="#7d7d82"/>';

  const PLATFORM =
    '<rect x="158" y="176" width="100" height="24" rx="4" fill="#ffd500"/>' +
    [...Array(4)].map((_, i) => `<circle cx="${176 + i * 22}" cy="176" r="4" fill="#e0bc00"/>`).join('');

  const MOTOR2 =
    '<rect x="164" y="136" width="42" height="40" rx="6" fill="#9a9aa0"/>' +
    '<circle cx="206" cy="156" r="8" fill="#6e6e72"/>';

  const BEAM =
    '<rect x="206" y="146" width="128" height="20" rx="9" fill="#0055bf"/>' +
    [...Array(4)].map((_, i) => `<circle cx="${228 + i * 28}" cy="156" r="5" fill="#003c86"/>`).join('');

  const MOTOR3 =
    '<rect x="316" y="132" width="36" height="34" rx="6" fill="#9a9aa0"/>' +
    '<circle cx="352" cy="149" r="6" fill="#6e6e72"/>';

  const GRIPPER =
    '<circle cx="356" cy="130" r="11" fill="#237841"/><circle cx="356" cy="130" r="4" fill="#145232"/>' +
    '<path d="M358 120 q24 -14 34 -4" stroke="#ffd500" stroke-width="7" fill="none" stroke-linecap="round"/>' +
    '<path d="M360 140 q24 12 32 4" stroke="#ffd500" stroke-width="7" fill="none" stroke-linecap="round"/>';

  const CABLES =
    '<path d="M207 252 q-40 24 -123 -14" stroke="#6b6b70" stroke-width="3" fill="none"/>' +
    '<path d="M170 156 q-70 10 -86 52" stroke="#6b6b70" stroke-width="3" fill="none"/>' +
    '<path d="M322 166 q-60 70 -238 46" stroke="#6b6b70" stroke-width="3" fill="none"/>';

  const ARROW_DEFS =
    '<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">' +
    '<path d="M0,0 L10,5 L0,10 z" fill="#d01012"/></marker></defs>';

  const svg = (inner) =>
    `<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg" role="img">${ARROW_DEFS}${inner}</svg>`;

  const label = (x, y, text, anchor = 'middle') =>
    `<text x="${x}" y="${y}" fill="#cfcfcf" font-size="14" font-weight="bold" text-anchor="${anchor}" font-family="sans-serif">${text}</text>`;

  // Full assembly at normal opacity, for intro/finale scenes.
  const FULL = PLATE + HUB + MOTOR1 + PLATFORM + MOTOR2 + BEAM + MOTOR3 + GRIPPER + CABLES;

  return { g, svg, label, PLATE, HUB, MOTOR1, PLATFORM, MOTOR2, BEAM, MOTOR3, GRIPPER, CABLES, FULL };
})();

const BUILD_STEPS = (() => {
  const { g, svg, label, PLATE, HUB, MOTOR1, PLATFORM, MOTOR2, BEAM, MOTOR3, GRIPPER, CABLES, FULL } = ARM_SVG;
  return [
    {
      caption: 'This is what you’re building: a robotic arm with a spinning base, a lifting shoulder, and a gripper — powered by the Technic Large Hub (88016).',
      svg: svg(
        FULL +
        '<line x1="207" y1="235" x2="150" y2="285" stroke="#888" stroke-width="1.5"/>' + label(130, 292, 'Base') +
        '<line x1="185" y1="150" x2="120" y2="110" stroke="#888" stroke-width="1.5"/>' + label(100, 104, 'Shoulder') +
        '<line x1="370" y1="120" x2="360" y2="70" stroke="#888" stroke-width="1.5"/>' + label(350, 62, 'Gripper')
      ),
    },
    {
      caption: 'Round up your parts and tick them off below: the 88016 hub, 3 motors, and Technic beams, pins, axles and gears.',
      svg: svg(
        '<rect x="20" y="40" width="360" height="220" rx="14" fill="none" stroke="#555" stroke-width="2" stroke-dasharray="8 6"/>' +
        '<g transform="translate(30,-120)">' + HUB + '</g>' + label(63, 160, 'Hub 88016') +
        '<g transform="translate(-45,-100)">' + MOTOR1 + '</g>' + label(162, 160, 'x3') +
        '<g transform="translate(5,-100)">' + MOTOR1 + '</g>' +
        '<g transform="translate(55,-100)">' + MOTOR1 + '</g>' +
        '<g transform="translate(20,30)">' + BEAM + '</g>' +
        '<g transform="translate(-120,40)">' + PLATFORM + '</g>' +
        '<circle cx="330" cy="225" r="14" fill="#237841"/><circle cx="330" cy="225" r="5" fill="#145232"/>' +
        label(330, 258, 'Gears')
      ),
    },
    {
      caption: 'Charge the hub first! Plug a USB-C cable into the hub and let it fill up while you build.',
      svg: svg(
        '<g transform="translate(118,-214) scale(1.6)">' + HUB + '</g>' +
        '<path d="M30 272 h100 q30 0 30 -30 v-27" stroke="#6b6b70" stroke-width="6" fill="none" stroke-linecap="round"/>' +
        '<rect x="152" y="199" width="16" height="18" rx="3" fill="#6b6b70"/>' +
        '<path d="M205 115 l-14 26 h12 l-10 24 26 -30 h-12 l12 -20 z" fill="#ffd500"/>'
      ),
    },
    {
      caption: 'Step 1 of the build: make a flat, sturdy base plate. This part never moves — everything else stands on it.',
      svg: svg(g('', PLATE)),
    },
    {
      caption: 'Stand motor #1 on the plate with its shaft pointing UP. This motor will spin the whole arm left and right.',
      svg: svg(
        g('dim', PLATE) + g('', MOTOR1) +
        '<line x1="207" y1="150" x2="207" y2="192" stroke="#d01012" stroke-width="4" marker-end="url(#ah)"/>'
      ),
    },
    {
      caption: 'Build the turntable platform onto motor #1’s shaft. Give it a spin with your hand — it should turn freely.',
      svg: svg(
        g('dim', PLATE + MOTOR1) + g('', PLATFORM) +
        '<path d="M150 168 q57 -26 116 0" stroke="#d01012" stroke-width="4" fill="none" marker-end="url(#ah)"/>'
      ),
    },
    {
      caption: 'Mount motor #2 on the platform, shaft pointing SIDEWAYS. This is the shoulder that lifts the arm.',
      svg: svg(
        g('dim', PLATE + MOTOR1 + PLATFORM) + g('', MOTOR2) +
        '<line x1="185" y1="90" x2="185" y2="126" stroke="#d01012" stroke-width="4" marker-end="url(#ah)"/>'
      ),
    },
    {
      caption: 'Attach the arm beam to motor #2’s shaft. Keep it short and light for now — a long heavy arm will sag.',
      svg: svg(
        g('dim', PLATE + MOTOR1 + PLATFORM + MOTOR2) + g('', BEAM) +
        '<path d="M330 190 q20 -14 10 -32" stroke="#d01012" stroke-width="4" fill="none" marker-end="url(#ah)"/>'
      ),
    },
    {
      caption: 'Fix motor #3 at the far end of the arm. This small worker will drive the gripper jaws.',
      svg: svg(
        g('dim', PLATE + MOTOR1 + PLATFORM + MOTOR2 + BEAM) + g('', MOTOR3) +
        '<line x1="334" y1="90" x2="334" y2="122" stroke="#d01012" stroke-width="4" marker-end="url(#ah)"/>'
      ),
    },
    {
      caption: 'Build the gripper: a gear on motor #3’s shaft turns the jaws so they pinch open and closed. Keep it light!',
      svg: svg(
        g('dim', PLATE + MOTOR1 + PLATFORM + MOTOR2 + BEAM + MOTOR3) + g('', GRIPPER) +
        '<path d="M390 102 q-8 26 0 52" stroke="#d01012" stroke-width="4" fill="none" marker-start="url(#ah)" marker-end="url(#ah)"/>'
      ),
    },
    {
      caption: 'Plug the cables into the hub: base motor → port A, shoulder → port B, gripper → port C.',
      svg: svg(
        '<rect x="90" y="60" width="220" height="180" rx="18" fill="#f2f2f2"/>' +
        '<circle cx="200" cy="150" r="22" fill="#dcdcdc" stroke="#b5b5b5" stroke-width="3"/>' +
        '<rect x="80" y="84" width="22" height="26" rx="4" fill="#333"/>' +
        '<text x="112" y="103" fill="#333" font-size="16" font-weight="bold" font-family="sans-serif">A</text>' +
        '<rect x="80" y="137" width="22" height="26" rx="4" fill="#333"/>' +
        '<text x="112" y="156" fill="#333" font-size="16" font-weight="bold" font-family="sans-serif">B</text>' +
        '<rect x="80" y="190" width="22" height="26" rx="4" fill="#333"/>' +
        '<text x="112" y="209" fill="#333" font-size="16" font-weight="bold" font-family="sans-serif">C</text>' +
        '<rect x="298" y="84" width="22" height="26" rx="4" fill="#555"/>' + label(336, 102, 'D', 'start') +
        '<rect x="298" y="137" width="22" height="26" rx="4" fill="#555"/>' + label(336, 155, 'E', 'start') +
        '<rect x="298" y="190" width="22" height="26" rx="4" fill="#555"/>' + label(336, 208, 'F', 'start') +
        '<path d="M10 97 h68" stroke="#0055bf" stroke-width="5"/>' + label(30, 88, 'Base') +
        '<path d="M10 150 h68" stroke="#237841" stroke-width="5"/>' + label(34, 141, 'Shoulder') +
        '<path d="M10 203 h68" stroke="#d01012" stroke-width="5"/>' + label(34, 194, 'Gripper')
      ),
    },
    {
      caption: 'Cable check! Spin the base and lift the arm by hand — every cable needs slack through the WHOLE move. A tight cable will yank or stall.',
      svg: svg(
        FULL +
        '<path d="M120 275 q87 30 170 0" stroke="#d01012" stroke-width="4" fill="none" marker-start="url(#ah)" marker-end="url(#ah)"/>' +
        '<path d="M368 175 q14 -40 -6 -78" stroke="#d01012" stroke-width="4" fill="none" marker-start="url(#ah)" marker-end="url(#ah)"/>'
      ),
    },
    {
      caption: 'Press the hub’s center button to turn it on. The light ring wakes up — your arm is alive!',
      svg: svg(
        '<g transform="translate(118,-214) scale(1.6)">' + HUB + '</g>' +
        '<circle cx="200" cy="154" r="26" fill="none" stroke="#237841" stroke-width="4"/>' +
        '<g stroke="#ffd500" stroke-width="3" stroke-linecap="round">' +
        '<line x1="158" y1="78" x2="170" y2="90"/><line x1="242" y1="78" x2="230" y2="90"/>' +
        '<line x1="200" y1="62" x2="200" y2="80"/></g>'
      ),
    },
    {
      caption: 'Built! Tap “Try it!” to connect and drive your arm — USB cable to a computer is the most reliable way. Use Nudge A/B/C to check each motor landed on the right port.',
      svg: svg(
        FULL +
        '<g fill="#ffd500"><path d="M60 60 l6 14 14 2 -10 10 3 15 -13 -8 -13 8 3 -15 -10 -10 14 -2 z"/>' +
        '<path d="M330 40 l5 11 11 2 -8 8 2 12 -10 -6 -10 6 2 -12 -8 -8 11 -2 z"/>' +
        '<path d="M120 30 l4 9 9 1 -7 7 2 10 -8 -5 -8 5 2 -10 -7 -7 9 -1 z"/></g>'
      ),
    },
  ];
})();

document.addEventListener('DOMContentLoaded', () => {
  const statusEl = document.getElementById('status');
  const logEl = document.getElementById('log');

  const callbacks = {
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
  };

  const btHub = new ArmHub(callbacks);
  const usbHub = new UsbArmHub(callbacks);

  // Facade: the Test-tab buttons drive whichever backend is connected
  // (USB wins if somehow both are). Falls back to Bluetooth so "not
  // connected" messages still appear in the log.
  const hub = {
    get active() {
      return usbHub.isConnected ? usbHub : btHub;
    },
    moveBase(d) { this.active.moveBase(d); },
    moveShoulder(d) { this.active.moveShoulder(d); },
    moveGripper(a) { this.active.moveGripper(a); },
    stopAll() { this.active.stopAll(); },
    nudge(p) { this.active.nudge(p); },
    log(line) { callbacks.onLog(line); },
    // Settings setters live on the Bluetooth backend, which persists them
    // to localStorage; the USB backend reads the same keys live.
    setBasePort(p) { btHub.setBasePort(p); },
    setShoulderPort(p) { btHub.setShoulderPort(p); },
    setGripperPort(p) { btHub.setGripperPort(p); },
    setSpeed(v) { btHub.setSpeed(v); },
    setMoveSeconds(v) { btHub.setMoveSeconds(v); },
    get basePort() { return btHub.basePort; },
    get shoulderPort() { return btHub.shoulderPort; },
    get gripperPort() { return btHub.gripperPort; },
    get speed() { return btHub.speed; },
    get moveSeconds() { return btHub.moveSeconds; },
  };

  // --- Tabs ---
  function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === 'tab-' + name));
  }
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // --- Guide tab: parts checklist persistence ---
  document.querySelectorAll('#partsChecklist input[type="checkbox"]').forEach((box) => {
    const key = 'armPart_' + box.dataset.key;
    box.checked = localStorage.getItem(key) === '1';
    box.addEventListener('change', () => {
      localStorage.setItem(key, box.checked ? '1' : '0');
    });
  });

  // --- Guide tab: LEGO-instructions-style step pager ---
  const stepViewport = document.getElementById('stepViewport');
  const stepCaption = document.getElementById('stepCaption');
  const stepCounter = document.getElementById('stepCounter');
  const stepProgressFill = document.getElementById('stepProgressFill');
  const prevStepBtn = document.getElementById('prevStepBtn');
  const nextStepBtn = document.getElementById('nextStepBtn');
  const partsChecklistWrap = document.getElementById('partsChecklistWrap');
  const stepDoneRow = document.getElementById('stepDoneRow');
  const PARTS_STEP = 1; // the "round up your parts" page shows the checklist
  const LAST_STEP = BUILD_STEPS.length - 1;

  let stepIndex = Math.min(
    LAST_STEP,
    Math.max(0, parseInt(localStorage.getItem('armBuildStep') || '0', 10) || 0)
  );

  function showStep(i) {
    stepIndex = Math.min(LAST_STEP, Math.max(0, i));
    localStorage.setItem('armBuildStep', String(stepIndex));
    stepViewport.innerHTML = BUILD_STEPS[stepIndex].svg;
    stepCaption.textContent = BUILD_STEPS[stepIndex].caption;
    stepCounter.textContent = `Step ${stepIndex + 1} / ${BUILD_STEPS.length}`;
    stepProgressFill.style.width = ((stepIndex + 1) / BUILD_STEPS.length) * 100 + '%';
    partsChecklistWrap.hidden = stepIndex !== PARTS_STEP;
    stepDoneRow.hidden = stepIndex !== LAST_STEP;
    prevStepBtn.disabled = stepIndex === 0;
    nextStepBtn.disabled = stepIndex === LAST_STEP;
  }

  prevStepBtn.addEventListener('click', () => showStep(stepIndex - 1));
  nextStepBtn.addEventListener('click', () => showStep(stepIndex + 1));
  document.getElementById('goTestBtn').addEventListener('click', () => switchTab('test'));
  document.getElementById('goWiringBtn').addEventListener('click', () => switchTab('wiring'));

  // Swipe left/right on the picture to page, like the LEGO app.
  let touchStartX = null;
  stepViewport.addEventListener('touchstart', (e) => { touchStartX = e.changedTouches[0].clientX; }, { passive: true });
  stepViewport.addEventListener('touchend', (e) => {
    if (touchStartX === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX;
    touchStartX = null;
    if (dx < -40) showStep(stepIndex + 1);
    else if (dx > 40) showStep(stepIndex - 1);
  }, { passive: true });

  // Arrow keys on desktop, only while the Guide tab is showing.
  document.addEventListener('keydown', (e) => {
    if (!document.getElementById('tab-guide').classList.contains('active')) return;
    if (e.key === 'ArrowRight') showStep(stepIndex + 1);
    else if (e.key === 'ArrowLeft') showStep(stepIndex - 1);
  });

  showStep(stepIndex);

  // --- Test tab: connect ---
  document.getElementById('connectBtn').addEventListener('click', () => {
    if (usbHub.isConnected) usbHub.disconnect();
    btHub.connect();
  });
  document.getElementById('usbConnectBtn').addEventListener('click', () => {
    if (btHub.isConnected) btHub.disconnect();
    usbHub.connect();
  });
  document.getElementById('disconnectBtn').addEventListener('click', () => {
    if (usbHub.isConnected) usbHub.disconnect();
    if (btHub.isConnected) btHub.disconnect();
  });

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
