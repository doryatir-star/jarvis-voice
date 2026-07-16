// EXPERIMENTAL push-to-talk voice for the rover, using offline in-browser
// Whisper (transformers.js) instead of Apple's Web Speech API — because Apple
// blocks Web Speech in WKWebView browsers like Bluefy. Adapted from the
// Whisper hold-to-talk path in the older docs/index.html (lines 550-641).
//
// The microphone opens only while the button is held, and every mic track is
// stopped on release so the Bluetooth connection has the best chance to
// resume. Commands run AFTER release + transcription, by which point the hub
// auto-reconnect may have recovered the connection. Diagnostics are logged so
// we learn exactly what happens — this is a genuine experiment, not a
// guaranteed fix. If merely opening the mic severs Bluetooth in Bluefy, this
// may still not work.

class HoldToTalk {
  constructor({ hub, onLog, onStatus } = {}) {
    this.hub = hub;
    this.onLog = onLog || (() => {});
    this.onStatus = onStatus || (() => {});
    this.synth = window.speechSynthesis || null;

    this._whisper = null;
    this._whisperLoading = false;
    this._stream = null;
    this._recorder = null;
    this._chunks = [];
    this._active = false;
  }

  async _ensureWhisper() {
    if (this._whisper) return this._whisper;
    if (this._whisperLoading) {
      while (!this._whisper) await new Promise((r) => setTimeout(r, 150));
      return this._whisper;
    }
    this._whisperLoading = true;
    this.onLog('Loading voice engine (~40 MB, one-time download)…');
    this.onStatus('loading');
    // esm.sh serves a proper ES module for this package.
    const mod = await import('https://esm.sh/@xenova/transformers@2.17.2');
    mod.env.allowLocalModels = false;
    mod.env.useBrowserCache = true;
    this._whisper = await mod.pipeline('automatic-speech-recognition', 'Xenova/whisper-tiny.en', {
      quantized: true,
      progress_callback: (p) => {
        if (p.status === 'progress' && typeof p.progress === 'number') {
          this.onStatus('loading ' + p.progress.toFixed(0) + '%');
        }
      },
    });
    this._whisperLoading = false;
    this.onLog('Voice engine ready. Hold the button and speak.');
    this.onStatus('ready');
    return this._whisper;
  }

  async _blobToMono16k(blob) {
    const ab = await blob.arrayBuffer();
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const buf = await ac.decodeAudioData(ab);
    ac.close();
    const src = buf.getChannelData(0);
    const srcRate = buf.sampleRate;
    if (srcRate === 16000) return src;
    const ratio = srcRate / 16000;
    const outLen = Math.floor(src.length / ratio);
    const out = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) out[i] = src[Math.floor(i * ratio)];
    return out;
  }

  async press() {
    if (this._active) return;
    this._active = true;
    const wasConnected = this.hub && this.hub.isConnected;
    this.onLog(`(diagnostic) hub connected before mic: ${wasConnected}`);
    try {
      this._stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      this._active = false;
      this.onLog('Microphone permission denied or unavailable: ' + e.message);
      this.onStatus('blocked');
      return;
    }
    const nowConnected = this.hub && this.hub.isConnected;
    this.onLog(`(diagnostic) hub connected after mic opened: ${nowConnected}`);
    if (wasConnected && !nowConnected) {
      this.onLog('Note: opening the mic dropped the hub — will try to reconnect on release.');
    }
    this._chunks = [];
    try {
      this._recorder = new MediaRecorder(this._stream);
    } catch (e) {
      this.onLog('Recording not supported in this browser: ' + e.message);
      this._releaseMic();
      this._active = false;
      return;
    }
    this._recorder.ondataavailable = (e) => { if (e.data && e.data.size) this._chunks.push(e.data); };
    this._recorder.start();
    this.onStatus('recording');
    // Warm up the model in parallel (first time downloads ~40 MB).
    this._ensureWhisper().catch((e) => this.onLog('Voice engine failed: ' + e.message));
  }

  _releaseMic() {
    if (this._stream) {
      // Fully release the mic so Bluetooth can resume.
      this._stream.getTracks().forEach((t) => { try { t.stop(); } catch (e) { /* noop */ } });
      this._stream = null;
    }
  }

  async release() {
    if (!this._active) return;
    this._active = false;
    if (!this._recorder || this._recorder.state !== 'recording') {
      this._releaseMic();
      return;
    }
    this.onStatus('transcribing');
    await new Promise((r) => { this._recorder.onstop = r; this._recorder.stop(); });
    const mime = this._recorder.mimeType || 'audio/webm';
    const blob = new Blob(this._chunks, { type: mime });
    this._releaseMic();

    // We're still inside (or just after) the button-up gesture — best chance
    // iOS lets us re-establish the BLE link if the mic dropped it.
    if (this.hub && !this.hub.isConnected && typeof this.hub.tryReconnect === 'function') {
      this.onLog('Reconnecting the hub after releasing the mic…');
      this.hub.tryReconnect();
    }

    if (blob.size < 800) { this.onStatus('ready'); return; }
    try {
      const audio = await this._blobToMono16k(blob);
      const w = await this._ensureWhisper();
      const out = await w(audio, { sampling_rate: 16000 });
      const text = (out.text || '').trim();
      if (!text) { this.onStatus('ready'); return; }
      this.onLog('“' + text + '”');
      this._run(text);
    } catch (e) {
      this.onLog('Transcription failed: ' + e.message);
    } finally {
      this.onStatus('ready');
    }
  }

  _run(text) {
    // stripWake/matchRoverIntent come from voice.js. A wake word isn't needed
    // for push-to-talk, but accept an optional "hey jarvis" prefix.
    const stripped = (typeof stripWake === 'function') ? stripWake(text) : { cmd: text, matched: false };
    const payload = (stripped.matched ? stripped.cmd : text).trim() || text;
    const intent = (typeof matchRoverIntent === 'function') ? matchRoverIntent(payload) : null;
    if (!intent) {
      this._say("I didn't catch a command.");
      this.onLog('(no matching command)');
      return;
    }
    if (this.hub && !this.hub.isConnected) {
      this.onLog("Heard “" + payload + "” but the hub isn't connected yet — tap Connect, then try again.");
      this._say("The hub isn't connected.");
      return;
    }
    try {
      if (intent.arg === undefined) this.hub[intent.method]();
      else this.hub[intent.method](intent.arg);
      this._say(intent.say);
    } catch (e) {
      this.onLog('Command failed: ' + e.message);
    }
  }

  _say(text) {
    if (!text || !this.synth) return;
    try {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.05;
      u.pitch = 0.95;
      this.synth.cancel();
      this.synth.speak(u);
    } catch (e) { /* noop */ }
  }
}
