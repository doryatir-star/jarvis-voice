// "Hey Jarvis" voice control for the rover, using the browser's built-in Web
// Speech API (SpeechRecognition) for listening and speechSynthesis for
// talking back. Patterns reused from the older docs/index.html JARVIS page.
//
// IMPORTANT: Apple restricts SpeechRecognition in third-party iOS browsers,
// so this may not work in Bluefy. VoiceAssistant.isSupported reports that,
// and the UI degrades to "use the buttons" rather than breaking.

// --- Wake word ---
// Includes common mishearings of "jarvis" from speech engines.
const WAKE_WORDS = [
  'hey jarvis', 'ok jarvis', 'okay jarvis', 'jarvis',
  'jervis', 'jarvi', 'service', 'travis', 'charles', 'harvey', 'jarvie',
];

/** Strips a leading wake word. Returns { cmd, matched }. If the whole
 * utterance IS just the wake word, cmd is "" but matched is true. */
function stripWake(text) {
  const t = text.trim().toLowerCase().replace(/^[,.\s]+/, '');
  const sorted = WAKE_WORDS.slice().sort((a, b) => b.length - a.length);
  for (const w of sorted) {
    if (t === w) return { cmd: '', matched: true };
    if (t.startsWith(w + ' ') || t.startsWith(w + ',') || t.startsWith(w + '.')) {
      return { cmd: t.slice(w.length).replace(/^[\s,.?!]+/, ''), matched: true };
    }
  }
  return { cmd: text, matched: false };
}

/** Maps a natural-language command (wake word already stripped) to a rover
 * action. Returns { method, arg, say } or null if nothing matched. Ordered
 * most-specific first. `method`/`arg` name a RoverHub method + argument. */
function matchRoverIntent(text) {
  // Normalize: lowercase, drop filler words and punctuation. Note we do NOT
  // strip "go" — it's part of "let go" (claw open).
  let t = ' ' + text.toLowerCase().replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim() + ' ';
  t = t.replace(/\b(please|now|the|your|a|to|and|then|rover|robot|jarvis)\b/g, ' ');
  t = ' ' + t.replace(/\s+/g, ' ').trim() + ' ';
  const has = (re) => re.test(t);

  // Stop first — it's the safety command, should win over everything.
  if (has(/\b(stop|halt|freeze|brake|whoa|wait|hold on)\b/)) {
    return { method: 'stopAll', arg: undefined, say: 'Stopping.' };
  }

  // Head — check before plain left/right so "look left" isn't a drive-turn.
  if (has(/\b(head|look|face)\b/)) {
    if (has(/\bleft\b/)) return { method: 'turnHead', arg: 'left', say: 'Looking left.' };
    if (has(/\bright\b/)) return { method: 'turnHead', arg: 'right', say: 'Looking right.' };
    if (has(/\b(center|centre|straight|forward|ahead|middle|front)\b/))
      return { method: 'turnHead', arg: 'center', say: 'Head centered.' };
  }

  // Claw (open checked before close; both before drive/turn)
  if (has(/\b(open|release|let go|drop|ungrip|unclamp)\b/)) {
    return { method: 'claw', arg: 'open', say: 'Opening the claw.' };
  }
  if (has(/\b(close|grab|grip|pinch|hold|clamp|catch|clench|squeeze)\b/)) {
    return { method: 'claw', arg: 'close', say: 'Closing the claw.' };
  }

  // Turning (drive)
  if (has(/\b(left)\b/)) return { method: 'turn', arg: 'left', say: 'Turning left.' };
  if (has(/\b(right)\b/)) return { method: 'turn', arg: 'right', say: 'Turning right.' };

  // Backward — before forward, and catch "back up", "reverse".
  if (has(/\b(back|backward|backwards|backup|reverse|retreat)\b/)) {
    return { method: 'drive', arg: 'backward', say: 'Moving backward.' };
  }

  // Forward
  if (has(/\b(forward|forwards|ahead|straight|advance|onward|move|drive|go)\b/)) {
    return { method: 'drive', arg: 'forward', say: 'Moving forward.' };
  }

  // Connection
  if (has(/\b(connect|scan|pair|find|search)\b/)) {
    return { method: 'connect', arg: undefined, say: 'Scanning for the hub.' };
  }
  if (has(/\bdisconnect\b/)) {
    return { method: 'disconnect', arg: undefined, say: 'Disconnecting.' };
  }

  return null;
}

class VoiceAssistant {
  constructor({ hub, onLog, onState } = {}) {
    this.hub = hub;
    this.onLog = onLog || (() => {});
    this.onState = onState || (() => {});

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.isSupported = !!SR;
    this.running = false;
    this.enabled = true;
    this._speaking = false;
    this._muteUntil = 0;
    this._lastFinal = '';

    this.synth = window.speechSynthesis || null;

    if (this.isSupported) {
      this.recog = new SR();
      this.recog.continuous = true;
      this.recog.interimResults = true;
      this.recog.lang = 'en-US';
      this.recog.onresult = (ev) => this._onResult(ev);
      this.recog.onend = () => this._onEnd();
      this.recog.onerror = (ev) => this._onError(ev);
    } else {
      this.recog = null;
    }
  }

  /** Must be called from a user tap (iOS requires a gesture to unlock the
   * mic and speech synthesis). */
  start() {
    if (!this.isSupported) {
      this.onState('unsupported');
      this.onLog("Voice isn't available in this browser. On iPhone, Apple blocks it in Bluefy — use the on-screen buttons instead.");
      return;
    }
    if (this.running) return;
    this.running = true;
    this.enabled = true;
    if (this.synth) { try { this.synth.getVoices(); } catch (e) { /* warm voices */ } }
    try { this.recog.start(); } catch (e) { /* already started */ }
    this.onState('listening');
    this.onLog("Listening. Say “Hey Jarvis” then a command.");
    this.say('Online. Say Hey Jarvis, then a command.');
  }

  toggle() {
    if (!this.isSupported || !this.running) return;
    this.enabled = !this.enabled;
    if (this.enabled) {
      try { this.recog.start(); } catch (e) { /* noop */ }
      this.onState('listening');
    } else {
      try { this.recog.stop(); } catch (e) { /* noop */ }
      this.onState('paused');
    }
  }

  stop() {
    this.running = false;
    this.enabled = false;
    if (this.recog) { try { this.recog.stop(); } catch (e) { /* noop */ } }
    this.onState('idle');
  }

  _onResult(ev) {
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const res = ev.results[i];
      if (!res.isFinal) continue;
      const text = res[0].transcript.trim();
      if (!text || text === this._lastFinal) continue;
      this._lastFinal = text;

      // Ignore our own TTS being picked up by the mic.
      if (this._speaking || performance.now() < this._muteUntil) continue;

      const { cmd, matched } = stripWake(text);
      if (!matched) {
        this.onLog('[ignored] ' + text);
        continue;
      }
      this.onLog('“' + text + '”');
      if (!cmd) { this.say('Yes?'); continue; }
      this._run(cmd);
    }
  }

  _run(cmd) {
    const intent = matchRoverIntent(cmd);
    if (!intent) {
      this.say("I didn't catch that.");
      this.onLog('(no matching command)');
      return;
    }
    try {
      if (intent.arg === undefined) this.hub[intent.method]();
      else this.hub[intent.method](intent.arg);
      this.say(intent.say);
    } catch (e) {
      this.onLog('Command failed: ' + e.message);
      this.say('Something went wrong.');
    }
  }

  _onEnd() {
    // continuous recognition still stops on silence/timeout — restart it.
    if (this.running && this.enabled) {
      try { this.recog.start(); } catch (e) { /* noop */ }
    } else {
      this.onState(this.running ? 'paused' : 'idle');
    }
  }

  _onError(ev) {
    if (ev.error === 'no-speech' || ev.error === 'aborted') return;
    this.onLog('Voice error: ' + ev.error);
    if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
      this.onState('blocked');
      this.onLog('Allow microphone access for this site, then tap the mic again.');
    }
  }

  say(text) {
    if (!text || !this.synth) return;
    try {
      this._speaking = true;
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.05;
      u.pitch = 0.95;
      const voices = this.synth.getVoices();
      const pref = voices.find((v) => /UK|British|Daniel|Oliver|Google UK English Male/i.test(v.name))
        || voices.find((v) => /male/i.test(v.name))
        || voices[0];
      if (pref) u.voice = pref;
      u.onend = () => {
        this._speaking = false;
        this._muteUntil = performance.now() + 1200;
      };
      this.synth.cancel();
      this.synth.speak(u);
    } catch (e) {
      this._speaking = false;
    }
  }
}
